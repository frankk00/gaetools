# File: model.py
# This file is used to define the models required to run the twawler
# 
# Section: Version History
# 14/05/2009 (DJO) - Initial Version Created

# import standard libraries
import datetime
import logging

# import appengine libraries
from google.appengine.ext import db
from google.appengine.api import memcache

# import other gaetools libs
import cachehelper

class TwawlAuthRequest(db.Model):
    """
    This class is used to define the oauth access tokens for the users that may make use of the application
    """
    
    requestKey = db.StringProperty(required = False)
    requestKeyEncoded = db.StringProperty(required = False)
    accessKeyEncoded = db.StringProperty(required = False)
    
    def findByRequestKey(key):
        """
        This static method is used to find a user by the request key
        """
        
        # initialise the query
        query = TwawlAuthRequest.gql("WHERE requestKey = :key", key=key)
        
        # return the query result
        return query.get()
        
    def findOrCreate(key, allowCreate = True):
        """
        This static method is used to find or create the required user that will be used to 
        store the oauth request and access keys
        """
        
        # convert the user id to lower case
        fnresult = TwawlAuthRequest.findByRequestKey(key)
        
        # if we couldn't find the user then create him
        if allowCreate and (fnresult == None):
            fnresult = TwawlAuthRequest(requestKey = key)
            
        return fnresult
    
    findByRequestKey = staticmethod(findByRequestKey)
    findOrCreate = staticmethod(findOrCreate)
    
class TwawlRule(db.Model):
    """
    This class is used to define the model that encapsulates a particular rule of tweets that we are looking
    for in the system.  Twawl rules are used to group together relevant twawl history records
    """
    
    ruleName = db.StringProperty(required = True)
    lastSearch = db.DateTimeProperty(required = False)
    highTweetId = db.IntegerProperty(required = True, default = 0)
    totalTweets = db.IntegerProperty(required = True, default = 0)
    
    def update(self, highTweet, tweetsIncrement):
        """
        This method is used to update the details of the twawl rule and then clear the cache
        """
    
        # update the last search and high tweet id of the rule
        self.lastSearch = datetime.datetime.utcnow()
        self.highTweetId = highTweet 
        
        # update the total tweets of the rule
        if (self.totalTweets is None):
            self.totalTweets = tweetsIncrement
        else:
            self.totalTweets = self.totalTweets + tweetsIncrement
            
        # save the rule to the database
        self.put()
        
        # add an info log entry about the number of tweets processed
        logging.info("successfully processed %s tweets, high tweet id now %s", tweetsIncrement, highTweet)
        
        # clear the cache key for the update
        memcache.delete(cachehelper.createCacheKey("twawlrule", self.ruleName))
    
    def findOrCreate(searchName):
        # convert the rulename to lower case
        searchName = searchName.lower()
        
        # look for the twawl rule in the cache first
        fnresult = memcache.get(cachehelper.createCacheKey("twawlrule", searchName))
        if (fnresult is not None):
            logging.debug("Returned twawlrule %s from the cache", searchName)
            return fnresult

        # look for the specified rule where the rule name is a match
        query = TwawlRule.gql("WHERE ruleName = :name", name=searchName)
        
        # get the result from the query
        fnresult = query.get()
        
        # if we couldn't find the rule, then create a new one
        if (fnresult == None):
            fnresult = TwawlRule(ruleName = searchName)
            fnresult.put()
            
        # add the rule to the cache
        if not memcache.add(cachehelper.createCacheKey("twawlrule", searchName), fnresult):
            logging.error("Unable to write the twawl rule %s to the cache", searchName)
            
        return fnresult
    
    findOrCreate = staticmethod(findOrCreate)
    
    
class TwawlHistory(db.Model):
    """
    This class is used to define the model for SearchHistory as maintained in the system.  The search history for
    conceptbuzz will basically be a daily log of the number of tweets that were found overall and the id of the last
    tweet processed for that day.  In that way, we can optimize our search routine to only look for tweets that have
    occurred after the last tweet of the current days search history
    """
    
    # the daily high tweet id
    searchDate = db.DateProperty(required = True)
    
    # the number of tweets found for the day
    totalTweets = db.IntegerProperty(required = True)
    
    # the high tweet mark
    highTweetId = db.IntegerProperty(required = True)
    
    # the rule reference
    rule = db.ReferenceProperty(TwawlRule, required = True)
    
    def find(searchRule, searchDate):
        """
        This static method will be used to find the TwawlHistory.  First hitting the cache
        for information and then checking the databsae is not available.
        """
        
        # check the cache for the twawl history record
        fnresult = memcache.get(cachehelper.createCacheKey("twawlHistory", searchRule.ruleName, searchDate.isoformat()))
        
        # if found, return the value
        if fnresult is not None:
            logging.debug("returned TwawlHistory %s from the cache", fnresult)
            return fnresult
        
        # look for the specified date in the database
        query = TwawlHistory.gql("WHERE rule = :rule AND searchDate = :date", rule=searchRule, date=searchDate)
        
        # go looking for the result
        return query.get()
    
    def findOrCreateToday(ruleName):
        """
        This static method is used to find today's search history object.  NOTE: the method does not
        do a put to the database so as to minimize the number of writes to the database (as a write will
        be done at the end of the operation, we should leave that until then).
        """
        
        # look for the twawl rule
        searchRule = TwawlRule.findOrCreate(ruleName)
        
        # if the strUrl is blank, then set to a default
        fnresult = TwawlHistory.find(searchRule, datetime.datetime.utcnow().date())
        
        # if we didn't find the result, we better create a new one
        if (fnresult == None):
            fnresult = TwawlHistory(
                                     searchDate = datetime.datetime.utcnow().date()
                                     ,totalTweets = 0
                                     ,highTweetId = 0
                                     ,rule = searchRule
                                     )

            # since we found some tweets, we should update the twawl history
            
            
        return fnresult
    
    # define the static methods
    find = staticmethod(find)
    findOrCreateToday = staticmethod(findOrCreateToday)
    
class TweetSource(db.Model):
    """
    The twitter source class is used to define the source from which the tweet eminated
    """
    
    title = db.StringProperty(required = True)
    url = db.StringProperty(required = False)
    description = db.StringProperty(required = False)
    firstSeen = db.DateTimeProperty(required = True, default = datetime.datetime.utcnow())
    
    def findOrCreate(sourceString):
        """
        This static method is used to find the requested source type, and if not found then create
        it it the database
        """
        
        # convert the source string using BeautifulSoup
        soupedSource = BeautifulSoup(sourceString)
        
        logging.debug("Looking for source: %s", soupedSource)
        
        # firstly have a look in the cache
        # fnresult = memcache.get(cachehelper.createCacheKey("tweetsrc", title))
        
        return None
    
    findOrCreate = staticmethod(findOrCreate)

class TwitterUser(db.Model):
    """
    This model object is used to represent a user in twitter
    """
    
    userId = db.IntegerProperty(required = True)
    userName = db.StringProperty(required = False)
    profileImageUrl = db.StringProperty(required = False)
    
    def findOrCreate(id, name = None, imageUrl = None):
        """
        This static method is used to locate the user id, or create the new user as specified in the parameters.
        At this stage no caching is used in this method, but it could be updated to do so.  I just worry that the
        number of different users I expect to come across in twawling could mean that there is little value 
        in caching these details. 
        """
        
        # if the id is 0, then return None
        if (id is None) or (id == 0): 
            return None
        
        # initialise the query
        query = TwitterUser.gql("WHERE userId = :id", id=id)
        
        # return the first user found (should only be one)
        fnresult = query.get()
        
        # if we didn't find the user, then create a new TwitterUser record and save it to the database
        if fnresult is None:
            fnresult = TwitterUser(userId = id, userName = name, profileImageUrl = imageUrl)
            fnresult.put()
        # otherwise, if the username on the entry we found is empty, then we should update with the name if not empty
        elif (fnresult.userName is None) and (name is not None):
            fnresult.userName = name
            fnresult.profileImageUrl = imageUrl
            fnresult.put()
            
            
        return fnresult
        
    findOrCreate = staticmethod(findOrCreate)    
    
class Tweet(db.Model):
    """
    The Tweet class encapsulates details about a tweet from twitter.  At this stage the data stored in the model
    is related to the results of a search, but this will be extended as the gaetools library grows.
    """
    
    tweet_id = db.IntegerProperty(required = True)
    created_at = db.DateTimeProperty(required = True)
    from_user = db.ReferenceProperty(TwitterUser, required = True, collection_name = "TweetSrcUser_set")
    from_user_name = db.StringProperty(required = True)
    profile_image_url = db.StringProperty(required = False)
    to_user = db.ReferenceProperty(TwitterUser, required = False, collection_name = "TweetDestUser_set")
    text = db.StringProperty(required = True, multiline = True)
    iso_language_code = db.StringProperty(required = False)