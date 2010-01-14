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
        self.nextRequest = None
        self.processedCount = 0
        self.currentHistory = None
        
        # initialise function callbacks
        self.tweetInspectors = []
        
    def checkRequest(self, request):
        """
        This method is used to check the request for parameters that will affect the way we behave
        """
        
        # call inherited functionality
        slicer.SlicedTask.checkRequest(self, request)
        
        # initialise some members from the request
        self._allowInit = request.get('init', self._allowInit)
        self._oauth_token = request.get('oauth_token', self._oauth_token)
        
    def inspectTweet(self, tweet):
        """
        This method is used to iterate through all of the tweet inspectors that have expressed an interest
        in looking at tweets for this particular twawl, and calling them to have a look.  Tweet inspectors
        will make the decision about whether the tweet should be saved or not
        """
        
        # iterate through the inspectors, and tell them to have a look at the tweets
        for inspector in self.tweetInspectors:
            inspector(tweet)
        
    def processTweet(self, tweet):
        """
        This method is used to process a tweet and aggregate it into the database
        """
        
        # update the high tweet id
        if (tweet is not None):
            # increment the processed count
            self.processedCount += 1
            
            # inspect the tweet
            self.inspectTweet(tweet)
            
            # if we have been told to save the tweet, then save it to the database
            if tweet.worthSaving:
                tweet.save(self.currentHistory)

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
            request.nextPage = self.nextRequest
            request.searchQuery = self.twawlFor
            request.language = "en"
            
            logging.debug("High tweet id is %s", request.highTweetId)
            
            # make the request
            request.execute(self.processTweet)
            
            # if the request was not successful, return that we have finished immediately
            if not request.successful:
                return True
            
            # save the next page results, for if we get another shot
            self.nextRequest = request.nextPage
            
            # update the function result, based on the success of our search
            foundTweets = (request.nextPage is not None) or (self.highTweetId > request.highTweetId)
            fnresult = not foundTweets
            
            # if the request resulted in us finding some tweets, then update the history
            if foundTweets:         
                # get the search history for today
                self.currentHistory = twawlermodel.TwawlHistory.findOrCreateToday(self.ruleName)
                self.currentHistory.highTweetId = self.highTweetId
                
                # update the total tweets for the history
                if (self.currentHistory.totalTweets is None):
                    self.currentHistory.totalTweets = self.processedCount
                else:
                    self.currentHistory.totalTweets = self.currentHistory.totalTweets + self.processedCount  
                
                # save todays history
                self.currentHistory.put()
                
                # update the total tweets for the rule
                rule.update(self.highTweetId, self.processedCount)
            
        return fnresult
    
    def setCredentials(self, user, passwd):
        # initialise the username and password
        self.username = user
        self.password = passwd