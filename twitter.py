# File: twitter.py
# This file is used to define a simple interface into the twitter API.  For a more full-featured interface
# see http://code.google.com/p/python-twitter/ (however, I do use oauth).  Additionally, this module uses
# some specific GAE features to optimize performance so would likely have to be modified to run on another
# platform.
#
# Section: Version History
# 16/05/2009 (DJO) - Created File
# 15/01/2010 (DJO) - Modifications to the library to allow looser coupling

import datetime
import yaml
import logging
import exceptions

# import app engine libs
from google.appengine.api import memcache
from google.appengine.api import urlfetch

# import the django simplejson lib
from django.utils import simplejson

# import other libs
import oauth
import cachehelper

# TODO: remove the dependency on the TwawlUser library - twitter library needs to be stand-alone
import twawlermodel

# initialise some constants
# TODO: probably move these to configuration parameters, as they may change in the future
URL_REQUEST_TOKEN = 'http://twitter.com/oauth/request_token'
URL_ACCESS_TOKEN = 'http://twitter.com/oauth/access_token'
URL_AUTHORIZE = 'http://twitter.com/oauth/authorize'

ACTION_SEARCH = 'search.json'
ACTION_ACCOUNT_VERIFY = 'account/verify_credentials.json'
PARAM_NEXTPAGE = 'next_page'
DATETIME_FORMAT_TWITTER = "%a, %d %b %Y %H:%M:%S +0000"

# initialise some default values
DEFAULT_CONFIG = "twitter"

class TwitterConfig:
    """
    This class is used to read information for a particular user or twitter configuration from a 
    configuration file stored in the local filesystem. 
    """
    
    def __init__(self, config = DEFAULT_CONFIG):
        """
        Default constructor for the TwitterConfig class
        """
        
        # initialise members
        self.workerEmail = None
        self.consumerKey = None
        self.consumerSecret = None
        
        # initialise the request urls
        self.requestTokenUrl = URL_REQUEST_TOKEN
        self.accessTokenUrl = URL_ACCESS_TOKEN
        self.authorizeUrl = URL_AUTHORIZE
        
        # load the configuration from the specified configuration
        if config: 
            self.load(config)
    
    def load(self, config = DEFAULT_CONFIG):
        """
        Load the required config from the cache or configuration file if not available
        """
        
        # check to see if the config is currently cached
        dataMap = memcache.get(cachehelper.createCacheKey("twitter-config", config))

        # if the dataMap is not cached, then load it from the yaml in the filesystem
        if dataMap is None:           
            # open the required configuration file (using the conf directory)
            # TODO: fix this rather silly path
            fHandle = open('../../conf/' + config + '.yaml')
            
            # now read the configuration information, and then close the file
            try:
                dataMap = yaml.load(fHandle)

                # save the datamap to the cache
                memcache.set(cachehelper.createCacheKey("twitter-config", config), dataMap)
            finally:
                fHandle.close()
            
        # update the data based on the configuration data
        self.consumerKey = dataMap.get('consumerKey', None)
        self.consumerSecret = dataMap.get('consumerSecret', None)
        
        # add some logging
        logging.debug("consumerKey = %s", self.consumerKey)
            
class TwitterAuthRequiredException(Exception):
    """
    The TwitterAuthRequiredException exception is raised when a twitter authentication problem has occurred.  This is 
    most often the case when we are required to authenticate a user and we want to bubble the exception
    right up to the surface so we can redirect the user to an appropriate location.
    """
    
    def __init__(self, authUrl):
        """
        Initialise the exception details
        """
        # initialise members
        self.authorizationUrl = authUrl

class TwitterAuth:
    """
    This class is used to wrap the twitter oauth request and make it very simple to authenticate
    with twitter.
    """
    
    def __init__(self, twitter_config, urlToken = None):
        """
        Initialise an instance of the TwitterAuth class that will enable us to create an oauth access
        token with twitter
        """
        
        # initialise the configuration
        self.config = twitter_config
        self.requestToken = urlToken
        self.accessToken = None
        
        # create the consumer
        self.consumer = oauth.OAuthConsumer(self.config.consumerKey, self.config.consumerSecret)
        
        # if the oauth token is not set, then prepare the request token and authorization steps
        if self.requestToken is None:           
            # create the request token
            self.requestToken = self._initRequestToken(URL_REQUEST_TOKEN)
            
            # authorize the request token
            self._authorizeToken()
        # otherwise, create an oauth token from the string passed to the function
        else:
            # look for the twitter user from the database
            requestKey = twawlermodel.TwawlAuthRequest.findByRequestKey(self.requestToken)
            
            # if we found the user
            if requestKey is not None:
                self.accessToken = oauth.OAuthToken.from_string(requestKey.requestKeyEncoded)

    def _authorizeToken(self):
        """
        This method is used to authorize the request token.  The method is complete as yet as it doesn't
        actually perform the redirection to twitter to enable a user to authorize a site to use their account.
        This is due to the fact that twawler currently is used as a background service.  Once I am building an 
        application that requires it, I will build the interface. 
        """
        
        # create the oauth request
        oauth_request = oauth.OAuthRequest.from_token_and_callback(token=self.requestToken, callback=None, http_url=URL_AUTHORIZE)
        
        logging.debug("need to call: %s", oauth_request.to_url())
        raise TwitterAuthRequiredException(oauth_request.to_url())
        
    def _initRequestToken(self, requestTokenUrl):
        """
        This method is used to initialise the request token so we can progress obtaining an access token 
        to access twitter.
        """
        # create and sign the oauth request
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_url=URL_REQUEST_TOKEN)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer, None)
        logging.debug("created auth request: %s", oauth_request)
        
        # send the request
        request_result = urlfetch.fetch(url = requestTokenUrl, headers = oauth_request.to_header())
        
        # if the response was successful, then process the response
        fnresult = None
        if request_result.status_code == 200:
            fnresult = oauth.OAuthToken.from_string(request_result.content)
            
            # look for the twawl user in the database
            request = twawlermodel.TwawlAuthRequest.findOrCreate(fnresult.key)
            
            # update the user request key details
            request.requestKeyEncoded = fnresult.to_string()
            
            # save the user to the database
            request.put()
        else:
            logging.warning("Unable to obtain request token, response was %s", request_result.content)
        
        logging.debug("received request token: %s", fnresult)
        
        return fnresult
            
    def buildAccessToken(self, accessTokenUrl):
        """
        This static method is used to contact twitter and build the access token that will permit
        us to access the twitter information stream
        """
        
        # if the request token has not been set, then don't attempt to get an access token
        if self.requestToken is None:
            logging.warning("Unable to contact twitter, no request token available.")
            return None
        
        # initialise the oauth request
        logging.debug("Attempting to build access token from request token '%s'", self.requestToken)
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token=self.accessToken, http_url=URL_ACCESS_TOKEN)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer, self.accessToken)
        
        # send the request
        request_result = urlfetch.fetch(url = accessTokenUrl, headers = oauth_request.to_header())
        
        # if the response was successful, then process the response
        fnresult = None
        if request_result.status_code == 200:
            fnresult = oauth.OAuthToken.from_string(request_result.content)
            
            # update the user to store the access token
            request = twawlermodel.TwawlAuthRequest.findOrCreate(self.requestToken)
            
            # update the user accesskey 
            request.accessKeyEncoded = fnresult.to_string()
            request.put()
        else:
            logging.warning("Unable to obtain access token: %s", request_result.content)
            
        logging.debug("received access token: %s", fnresult)

        if fnresult:
            return fnresult.to_string()
    
    def getAccessToken(twitter_config, allowInit = True, urlToken = None):
        """
        This static method is used to wrap the operations of authenticating with twitter.  In addition
        to prevent requerying twitter many times for the authentication token, this is stored in the 
        mem-cache (TODO: investigate security concerns) to optimize performance.  
        """
        
        # initialise variables
        fnresult = None
        
        logging.debug("Application requested Twitter Access Token: allowInit = %s, url auth token = %s", allowInit, urlToken)
        
        # if the oauth token is set, then we should regenerate the authentication token
        if urlToken is not None:
            # create the authenticator
            authenticator = TwitterAuth(twitter_config, urlToken)
            
            # build the access token
            fnresult = authenticator.buildAccessToken(URL_ACCESS_TOKEN)
            
            return fnresult
        
        # if the access key is still not known, then see if we can obtain it from the database
        if fnresult is None:
            fnresult = twawlermodel.TwawlAuthRequest.findByRequestKey(urlToken)
            
        # if we have a value, then return that value
        if fnresult is not None:
            logging.debug("oauth key for request key '%s' retrieved from the cache or db", urlToken)
            return fnresult
        
        # seeing as we haven't used the cache, let's get stuck into this (If we are permitted)       
        if allowInit:
            # TODO: make this work for more than just a default service user
            authenticator = TwitterAuth(twitter_config)
        else:
            logging.error("Unable to contact twitter, access token unknown")
        
        # return the access token
        return fnresult
    
    getAccessToken = staticmethod(getAccessToken)
    
class Tweet():
    """
    This class is used to represent a tweet from twitter.
    """
    
    def __init__(self, srcDict = None):
        """
        Default constructor for the tweet class
        """
        
        # initialise members
        self.id = 0
        self.created_at = datetime.datetime.utcnow()
        self.from_user = 0
        self.from_user_id = 0
        self.to_user_id = 0
        self.text = ''
        self.profile_image_url = ''
        self.source = ''
        self.iso_language_code = 'en'
        
        # initialise some flags 
        self.worthSaving = True
        
        # if the source dictionary is defined, then copy the details across
        if srcDict is not None:
            self.loadFromDict(srcDict)
            
    def __str__(self):
        """
        Return a string representation of the tweet
        """
        
        return "[" + str(self.id) +"] " + self.from_user + ": " + self.text
            
    def loadFromDict(self, srcDict):
        """
        This method is used to initialise the elements of the tweet from the json decoded format stored in a dict
        
        @srcDict the input dict object that contains the parameters for the tweet
        """
        
        # TODO: implement a more elegant way of doing this - I hate typing repetitive stuff...
        self.id = srcDict.get('id', 0)
        self.created_at = datetime.datetime.strptime(srcDict.get('created_at', self.created_at.strftime(DATETIME_FORMAT_TWITTER)), DATETIME_FORMAT_TWITTER)
        self.from_user = srcDict.get('from_user', self.from_user)
        self.from_user_id = srcDict.get('from_user_id', self.from_user_id)
        self.to_user_id = srcDict.get('to_user_id', self.to_user_id)
        self.text = srcDict.get('text', self.text)
        self.profile_image_url = srcDict.get('profile_image_url', self.profile_image_url)
        self.source = srcDict.get('source', self.source)
        self.iso_language_code = srcDict.get('iso_language_code', self.iso_language_code)
        
    def save(self, history):
        """
        The save method is used to save the specified tweet details to the database.  I considered using the model
        class to pass around, but opted for a lightweight POPO instead.  Thus we need to save the object.
        """
        
        # create the tweet model object
        dbTweet = twawlermodel.Tweet(tweet_id = self.id,
                                     created_at = self.created_at,
                                     from_user = twawlermodel.TwitterUser.findOrCreate(self.from_user_id, self.from_user, self.profile_image_url),
                                     from_user_name = self.from_user,
                                     profile_image_url = self.profile_image_url,
                                     to_user = twawlermodel.TwitterUser.findOrCreate(self.to_user_id),
                                     text = self.text,
                                     iso_language_code = self.iso_language_code)
        
        # save the tweet to the database
        dbTweet.put()
        
class TwitterRequest():
    """
    This class is used to define a base class for all other twitter requests.  The request handles
    authentication as required.
    """
    
    def __init__(self, allow_init = False, url_auth_token = None, twitter_config = None):
        """
        Initialise the twitter request
        """
        
        # initialise variables
        self.authRequired = True
        self.baseUrl = "http://twitter.com/"
        self.allowInit = allow_init
        self.urlAuthToken = url_auth_token
        self.accessToken = None
        self.successful = False
        
        # load the configuration information
        self.config = TwitterConfig() if (twitter_config is None) else twitter_config
        
    def execute(self, responseCallback = None):
        """
        The execute method is used to run the execute the request to twitter.  This method basically
        calls a number of methods that will be overriden in descendant classes to implement certain 
        behaviour.
        
        @reponseCallback - a function that will be executed if we successfully return a response
        """
        
        # initialise variables
        payload = {}
        token = None
        oauth_request = None
        
        # prepare the url
        nextAction = self.prepareRequest(payload)
        
        # if authentication is required, then prepare the request
        if self.authRequired:
            # create an oauth consumer
            consumer = oauth.OAuthConsumer(self.config.consumerKey, self.config.consumerSecret)
            
            # find the access key for the specified user
            self.accessToken = TwitterAuth.getAccessToken(self.config, self.allowInit, self.urlAuthToken)
            if self.accessToken is not None:
                logging.debug("attempting to parse access token: %s", self.accessToken)
                token = oauth.OAuthToken.from_string(self.accessToken)
            
            # create the oauth request
            if token is not None:
                oauth_request = oauth.OAuthRequest.from_consumer_and_token(consumer, token = token, http_url = nextAction)
                oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), consumer, token)
            else:
                logging.error("Request required authentication, however, no suitable access token available.")
        
        # if we have an oauth access key, then we can access twitter, otherwise, bail out.
        if (oauth_request is not None):
            # make the request
            logging.debug("Attempting to perform twitter api call: %s", nextAction)
            
            # alright make the request
            request_result = urlfetch.fetch(url = nextAction, headers = oauth_request.to_header())

            # if we received a request result, then process
            if (request_result.status_code == 200):
                self.successful = True
                logging.debug("Got successful response from api call, going to parse results: %s", request_result.content)
                
                # use simple json to decode the response
                self.processResponse(request_result.content, responseCallback)
            else:
                logging.warning("TWITTER SEARCH FAILED - STATUS CODE = %s", request_result.status_code)
        else:   
            logging.warning("TWITTER SEARCH NOT DONE, NO OAUTH INITIALIZATION PERMITTED")
            
class TwitterSearchRequest(TwitterRequest):
    """
    The TwitterSearchRequest class is used to wrap the search operation and return tweets that match a 
    certain request criteria
    """
    
    def __init__(self, allow_init = False, url_auth_token = None, twitter_config = None):
        """
        Initialise the search request
        """
        
        # call the inherited constructor
        TwitterRequest.__init__(self, allow_init, url_auth_token, twitter_config)
        
        # update the base url to the correct location
        self.nextPage = None
        self.baseUrl = "http://search.twitter.com/"
        self.language = None
        
        # initialise members
        self.highTweetId = 0
        self.searchQuery = ""
        self.tweets = []
        
    def prepareRequest(self, postParams):
        """
        The prepareRequest method is used to initialise the request in preparation to sending to twitter.  
        The method returns the url of the resource we are trying to access, and additionally post parameters
        can be pushed into the postParams argument.
        """
        
        # initialise variables
        fnresult = self.baseUrl + ACTION_SEARCH
        
        # if the next page is set, then use that url
        if self.nextPage is not None:
            fnresult += self.nextPage
        # otherwise, build a suitable url
        else:
            fnresult += "?rpp=50&q=" + oauth.escape(self.searchQuery) + "&since_id=" + str(self.highTweetId)
            
            # if the language code has been set, then specify the language code also
            if self.language is not None:
                fnresult += "&lang=" + self.language
            
        return fnresult
    
    def processResponse(self, content, responseCallback):
        """
        This method is used to process the response from twitter in the case that our request has been successful
        
        @content - the content of the response returned from the request
        @responseCallback - a method callback that can be used to push details back to the calling method
        """
        # decode the json response
        searchResults = simplejson.loads(content)
        logging.debug("TwitterSearchRequest processing the response")
        
        # check to see if we have a next page to process
        self.nextPage = None
        if (PARAM_NEXTPAGE in searchResults):
            logging.info("Another page of results found, will continue search")
            self.nextPage = searchResults[PARAM_NEXTPAGE]
        
        # iterate through the results
        if 'results' in searchResults:
            for singleResult in searchResults['results']:
                # create the new tweet instance
                tweetResult = Tweet(singleResult)
        
                # if the response callback is defined, then give it some information
                if responseCallback is not None:
                    responseCallback(tweetResult)
                    
                # add the tweet to the array
                self.tweets.append(tweetResult)
                
class TwitterLoginRequest(TwitterRequest):
    """
    The twitter verify request wrap the verify credentials api method and returns details about the specified
    user.
    """
    
    def __init__(self, allow_init = False, url_auth_token = None, twitter_config = None):
        """
        Initialise the twitter login request object
        """
        
        # call the inherited constructor
        TwitterRequest.__init__(self, allow_init, url_auth_token, twitter_config)
                
        # initialise members
        self.twitterId = 0
        self.screenName = None
        self.realName = None
        self.profileImageUrl = None
        self.location = 'The Twitterverse'
        self.followersCount = 0
        self.dateCreated = None
        self.utcOffset = 0

    def prepareRequest(self, postParams):
        """
        This method is used to prepare the request url and parameters for the required twitter API call
        """
        
        # initialise variables
        return self.baseUrl + ACTION_ACCOUNT_VERIFY
    
    def processResponse(self, content, responseCallback):
        """
        This method is used to process the response from twitter in the case that our request has been successful
        
        @content - the content of the response returned from the request
        @responseCallback - a method callback that can be used to push details back to the calling method
        """
        # decode the json response
        searchResults = simplejson.loads(content)
      
        # read the unique numeric id of the user from twitter
        self.twitterId = searchResults.get('id', self.twitterId)
        
        # read the current screen name (this can change)
        self.screenName = searchResults.get('screen_name', self.screenName)
        
        # read what they have specified as their contact name 
        self.realName = searchResults.get('name', self.realName)
        
        # read the url for the current avatar image
        self.profileImageUrl = searchResults.get('profile_image_url', self.profileImageUrl)
        
        # now get the bigger image
        self.profileImageUrl = self.profileImageUrl.replace("_normal.jpg", "_bigger.jpg")
        
        # read the location they have entered into their profile - may or may not be useful
        self.location = searchResults.get('location', self.location)
        
        # read the current number of followers that user has
        self.followersCount = searchResults.get('followersCount', self.followersCount)
        
        # read the date at which they signed up for twitter
        self.dateCreated = searchResults.get('created_at', self.followersCount)
        
        # read the utc offset they have specified for their account (in seconds)
        self.utcOffset = searchResults.get('utc_offset', self.utcOffset)
        
        logging.info("Successfully logged in %s (%d: %s from %s)", self.screenName, self.twitterId, self.realName, self.location)            
