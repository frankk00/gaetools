# File: model.py
# This file is used to define the models required to run the twawler
# 
# Section: Version History
# 14/05/2009 (DJO) - Initial Version Created

import datetime
import logging
import cachehelper

from google.appengine.ext import db
from google.appengine.api import memcache

class TwawlUser(db.Model):
    """
    This class is used to define the oauth access tokens for the users that may make use of the application
    """
    
    userId = db.StringProperty(required = True)
    requestKey = db.StringProperty(required = False)
    requestKeyEncoded = db.StringProperty(required = False)
    accessKeyEncoded = db.StringProperty(required = False)
    
    def findAccessKeyForUser(user):
        """
        This static method is used to look for a particular user, and if found then return the access
        key they have stored in the database
        """
        
        # initialise variable
        fnresult = None
        
        # look for the user
        user = TwawlUser.findOrCreate(user, False)
        
        # if we found the user, update the result
        if user is not None:
            fnresult = user.accessKeyEncoded
            
        return fnresult
    
    def findByRequestKey(key):
        """
        This static method is used to find a user by the request key
        """
        
        # initialise the query
        query = TwawlUser.gql("WHERE requestKey = :key", key=key)
        
        # return the query result
        return query.get()
        
    def findOrCreate(user, allowCreate = True):
        """
        This static method is used to find or create the required user that will be used to 
        store the oauth request and access keys
        """
        
        # convert the user id to lower case
        user = user.lower()
        
        # look for the specified user in the database
        query = TwawlUser.gql("WHERE userId = :user", user=user)
        
        # look for the result
        fnresult = query.get()
        
        # if we couldn't find the user then create him
        if allowCreate and (fnresult == None):
            fnresult = TwawlUser(userId = user)
            
        return fnresult
    
    findAccessKeyForUser = staticmethod(findAccessKeyForUser)
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