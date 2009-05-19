# File: twitter.py
# This file is used to define a simple interface into the twitter API.  For a more full-featured interface
# see http://code.google.com/p/python-twitter/ (however, I do use oauth).  Additionally, this module uses
# some specific GAE features to optimize performance so would likely have to be modified to run on another
# platform.
#
# Section: Version History
# 16/05/2009 (DJO) - Created File

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
from twawlermodel import TwawlUser

# initialise some constants
# TODO: probably move these to configuration parameters, as they may change in the future
URL_REQUEST_TOKEN = 'http://twitter.com/oauth/request_token'
URL_ACCESS_TOKEN = 'http://twitter.com/oauth/access_token'
URL_AUTHORIZE = 'http://twitter.com/oauth/authorize'

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
        
        # load the configuration from the specified configuration
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
            fHandle = open('conf/' + config + '.yaml')
            
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
    
    def __init__(self, twitUser, urlToken = None):
        """
        Initialise an instance of the TwitterAuth class that will enable us to create an oauth access
        token with twitter
        """
        
        # initialise the configuration
        # TODO: base this on the user
        self.userId = twitUser
        self.config = TwitterConfig()
        self.requestToken = None
        
        # create the consumer
        self.consumer = oauth.OAuthConsumer(self.config.consumerKey, self.config.consumerSecret)
        
        # if the oauth token is not set, then prepare the request token and authorization steps
        if urlToken is None:           
            # create the request token
            self.requestToken = self._initRequestToken(URL_REQUEST_TOKEN)
            
            # authorize the request token
            self._authorizeToken()
        # otherwise, create an oauth token from the string passed to the function
        else:
            # look for the twitter user from the database
            user = TwawlUser.findByRequestKey(urlToken)
            
            # if we found the user
            if user is not None:
                self.requestToken = oauth.OAuthToken.from_string(user.requestKeyEncoded)

    def _authorizeToken(self):
        """
        This method is used to authorize the request token.  The method is complete as yet as it doesn't
        actually perform the redirection to twitter to enable a user to authorize a site to use their account.
        This is due to the fact that twawler currently is used as a background service.  Once I am building an 
        application that requires it, I will build the interface. 
        """
        
        # create the oauth request
        oauth_request = oauth.OAuthRequest.from_token_and_callback(token=self.requestToken, callback=None,http_url=URL_AUTHORIZE)
        
        logging.debug("need to call: %s", oauth_request.to_url())
        raise TwitterAuthRequiredException(oauth_request.to_url())
        
        # perform the authorization
        # TODO: Do this optionally on callback to this application
        """
        request_result = urlfetch.fetch(oauth_request.to_url())
        
        fnresult = None
        if request_result.status_code == 200:
            logging.debug("Request Token Authorized")
        else:
            logging.warning("Request Token *NOT* Authorized")
        """
            
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
            user = TwawlUser.findOrCreate(self.userId)
            
            # update the user request key details
            user.requestKey = fnresult.key
            user.requestKeyEncoded = fnresult.to_string()
            
            # save the user to the database
            user.put()
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
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token=self.requestToken, http_url=URL_ACCESS_TOKEN)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer, self.requestToken)
        
        # send the request
        request_result = urlfetch.fetch(url = accessTokenUrl, headers = oauth_request.to_header())
        
        # if the response was successful, then process the response
        fnresult = None
        if request_result.status_code == 200:
            fnresult = oauth.OAuthToken.from_string(request_result.content)
            
            # update the user to store the access token
            user = TwawlUser.findOrCreate(self.userId)
            
            # update the user accesskey 
            user.accessKeyEncoded = fnresult.to_string()
            user.put()
        else:
            logging.warning("Unable to obtain access token: %s", request_result.content)
            
        logging.debug("received access token: %s", fnresult)

        return fnresult.to_string()
    
    def getAccessToken(userId, allowInit = True, urlToken = None, config = DEFAULT_CONFIG, allowCached = True):
        """
        This static method is used to wrap the operations of authenticating with twitter.  In addition
        to prevent requerying twitter many times for the authentication token, this is stored in the 
        mem-cache (TODO: investigate security concerns) to optimize performance.  
        """
        
        # initialise variables
        fnresult = None
        
        logging.debug("Application requested Twitter Access Token for user: %s, allowInit = %s, url auth token = %s", userId, allowInit, urlToken)
        
        # if the oauth token is set, then we should regenerate the authentication token
        if urlToken is not None:
            # create the authenticator
            authenticator = TwitterAuth(userId, urlToken)
            
            # build the access token
            fnresult = authenticator.buildAccessToken(URL_ACCESS_TOKEN)
            
            # cache the access token
            memcache.set(cachehelper.createCacheKey("twitter-token", userId), fnresult)
            
            return fnresult
        
        # if we are allowed to used a cached, entry check the cache
        if allowCached:
            fnresult = memcache.get(cachehelper.createCacheKey("twitter-token", userId))
            
        # if the access key is still not known, then see if we can obtain it from the database
        if fnresult is None:
            fnresult = TwawlUser.findAccessKeyForUser(userId)
            
        # if we have a value, then return that value
        if fnresult is not None:
            logging.debug("oauth key for user '%s' retrieved from the cache or db", userId)
            return fnresult
        
        # seeing as we haven't used the cache, let's get stuck into this (If we are permitted)       
        if allowInit:           
            # TODO: make this work for more than just a default service user
            authenticator = TwitterAuth(userId)           
        else:
            logging.error("Unable to contact twitter, access token for user '%s' unknown", userId)
        
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
        
        # if the source dictionary is defined, then copy the details across
        if srcDict is not None:
            self.loadFromDict(srcDict)
            
    def __str__(self):
        """
        Return a string representation of the tweet
        """
        
        return self.from_user + ": " + self.text
            
    def loadFromDict(self, srcDict):
        """
        This method is used to initialise the elements of the tweet from the json decoded format stored in a dict
        
        @srcDict the input dict object that contains the parameters for the tweet
        """
        
        # TODO: implement a more elegant way of doing this - I hate typing repetitive stuff...
        self.id = srcDict.get('id', 0)
        self.created_at = srcDict.get('created_at', self.created_at)
        self.from_user = srcDict.get('from_user', self.from_user)
        self.from_user_id = srcDict.get('from_user_id', self.from_user_id)
        self.to_user_id = srcDict.get('to_user_id', self.to_user_id)
        self.text = srcDict.get('text', self.text)
        self.profile_image_url = srcDict.get('profile_image_url', self.profile_image_url)
        self.source = srcDict.get('source', self.source)
        self.iso_language_code = srcDict.get('iso_language_code', self.iso_language_code)
        
class TwitterRequest():
    """
    This class is used to define a base class for all other twitter requests.  The request handles
    authentication as required.
    """
    
    def __init__(self, user = None):
        """
        Initialise the twitter request
        """
        
        # initialise variables
        self.userId = user
        self.authRequired = True
        self.baseUrl = "http://twitter.com/"
        self.allowInit = False
        self.urlAuthToken = None
        
        # load the configuration information
        self.config = TwitterConfig()
        
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
        url = self.prepareRequest(payload)
        
        # if authentication is required, then prepare the request
        if self.authRequired:
            # create an oauth consumer
            consumer = oauth.OAuthConsumer(self.config.consumerKey, self.config.consumerSecret)
            
            # find the access key for the specified user
            accessToken = TwitterAuth.getAccessToken(self.userId, self.allowInit, self.urlAuthToken)
            if accessToken is not None:
                logging.debug("attempting to parse access token: %s", accessToken)
                token = oauth.OAuthToken.from_string(accessToken)
            
            # create the oauth request
            if token is not None:
                oauth_request = oauth.OAuthRequest.from_consumer_and_token(consumer, token = token, http_url = url)
                oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), consumer, token)
            else:
                logging.error("Request required authentication, however, no suitable access token available.")
        
        if (oauth_request is not None):
            # make the request
            logging.debug("Attempting to perform twitter search: %s", url)
            
            # alright make the request
            request_result = urlfetch.fetch(url = url, headers = oauth_request.to_header())
            if (request_result.status_code == 200):
                logging.debug("Got successful response from search, going to parse results")
                
                # use simple json to decode the response
                self.processResponse(request_result.content, responseCallback)
            else:
                logging.warning("TWITTER SEARCH FAILED - RESPONSE: %s", request_status.content)
        else:   
            logging.warning("TWITTER SEARCH NOT DONE, NO OAUTH INITIALIZATION PERMITTED")
            
class TwitterSearchRequest(TwitterRequest):
    """
    The TwitterSearchRequest class is used to wrap the search operation and return tweets that match a 
    certain request criteria
    """
    
    def __init__(self, user = None):
        """
        Initialise the search request
        """
        
        # call the inherited constructor
        TwitterRequest.__init__(self, user)
        
        # update the base url to the correct location
        self.baseUrl = "http://search.twitter.com/"
        
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
        
        return self.baseUrl + "search.json?q=" + oauth.escape(self.searchQuery) + "&since_id=" + str(self.highTweetId)
    
    def processResponse(self, content, responseCallback):
        """
        This method is used to process the response from twitter in the case that our request has been successful
        
        @content - the content of the response returned from the request
        @responseCallback - a method callback that can be used to push details back to the calling method
        """

        # decode the json response
        logging.debug("TwitterSearchRequest processing the response, decoding the json")
        searchResults = simplejson.loads(content)
        
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