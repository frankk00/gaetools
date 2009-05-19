# File: tasks.py
# This file is used to define the tasks that twawler can execute to look for tweets
# 
# Section: Version History
# 14/05/2009 (DJO) - Created File

# import standard libraries
import string
import logging
import datetime

# import appengine libraries
from google.appengine.ext import db

# import local libraries
import twitter
import slicer
import twawlermodel

# define the minimum amount of time required to process some tweets
MIN_TWEET_PROCESSING_INTERVAL = datetime.timedelta(seconds = 5)

# define the twitter base search api
TWITTER_BASEURL = 'http://twitter.com/'
TWITTER_SEARCHURL = TWITTER_BASEURL + 'search.json?q=%s&since_id=%s'

class TwawlTask(slicer.SlicedTask):
    """
    The TweetSearchTask class is used to call the twitter search API and find tweets on 
    that match the #conceptbuzz label
    """
    
    def __init__(self, maxInterval = slicer.DEFAULT_MAX_INTERVAL):
        """
        Initialise the new TwawlTask object
        """
        
        # call the inherited constructor
        slicer.SlicedTask.__init__(self, maxInterval)
        
        # initialise private members
        self._allowInit = False
        self._oauth_token = None
        
        # initialise members
        self.userId = ''
        self.ruleName = ''
        self.highTweetId = 0
        self.twawlFor = 'A String that we are very unlikely to find...'
        self.processedCount = 0
        
    def checkRequest(self, request):
        """
        This method is used to check the request for parameters that will affect the way we behave
        """
        
        # call inherited functionality
        slicer.SlicedTask.checkRequest(self, request)
        
        # initialise some members from the request
        self._allowInit = request.get('init', self._allowInit)
        self._oauth_token = request.get('oauth_token', self._oauth_token)
        
    def processTweet(self, tweet):
        """
        This method is used to process a tweet and aggregate it into the database
        """
        
        # update the high tweet id
        if (tweet is not None):
            # increment the processed count
            self.processedCount += 1

            # if the tweet id is higher than the current high tweet id, then update
            if (tweet.id > self.highTweetId):
                self.highTweetId = tweet.id
            
        logging.debug("Processed a tweet: %s, tweets processed = %s", tweet, self.processedCount)
    
    def runTask(self, sliceAction):
        """
        In the context of this task we will perform the following operations:
        - check the amount of time remaining to make sure we have the minimum amount of time required to process some tweets
        - call the twitter search api and return up to 10 results to parse
        """
        
        # call inherited functionality 
        slicer.SlicedTask.runTask(self, sliceAction) 
        
        # check that we have got enough time to make a twitter api call
        fnresult = (self.getTimeRemaining() < MIN_TWEET_PROCESSING_INTERVAL)
        
        # if the twawl name is not set, then log a warning and mark as complete
        if (self.ruleName == ''):
            logging.warning("No twawl rule name is set, unable to twawl for tweets")
            fnresult = True
            
        # reset the processed count
        self.processedCount = 0 
               
        # if we haven't run out of time then carry on
        if (not fnresult):
            # get the rule instance
            rule = twawlermodel.TwawlRule.findOrCreate(self.ruleName)
            
            # create the twitter search request
            request = twitter.TwitterSearchRequest(self.userId)
            request.allowInit = self._allowInit
            request.urlAuthToken = self._oauth_token
            request.highTweetId = rule.highTweetId
            request.searchQuery = self.twawlFor
            
            logging.debug("High tweet id is %s", request.highTweetId)
            
            # make the request
            request.execute(self.processTweet) 
            
            # if the request resulted in us finding some tweets, then update the history
            if (self.highTweetId > request.highTweetId):         
                # get the search history for today
                todaysHistory = twawlermodel.TwawlHistory.findOrCreateToday(self.ruleName)
                todaysHistory.highTweetId = self.highTweetId
                
                # update the total tweets for the history
                if (todaysHistory.totalTweets is None):
                    todaysHistory.totalTweets = self.processedCount
                else:
                    todaysHistory.totalTweets = todaysHistory.totalTweets + self.processedCount  
                
                # save todays history
                todaysHistory.put()
                
                # update the total tweets for the rule
                rule.update(self.highTweetId, self.processedCount)
                
                # we found and processed some tweets, so we should have another look
                fnresult = False
            else:
                fnresult = True
            
        return fnresult
    
    def setCredentials(self, user, passwd):
        # initialise the username and password
        self.username = user
        self.password = passwd