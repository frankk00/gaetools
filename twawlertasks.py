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
from oauthmodel import OAuthAccessKey

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
    
    def __init__(self, run_as_user, twitter_config = None, maxInterval = slicer.DEFAULT_MAX_INTERVAL):
        """
        Initialise the new TwawlTask object
        """
        
        # call the inherited constructor
        slicer.SlicedTask.__init__(self, maxInterval)
        
        # initialise private members
        self._runAsUser = run_as_user
        self._accessKey = None
        self._twitterConfig = twitter_config
        
        # initialise members
        self.ruleName = ''
        self.highTweetId = 0
        self.searchFor = 'A String that we are very unlikely to find...'
        self.nextRequest = None
        self.processedCount = 0
        self.currentHistory = None
        self.searchType = "search"
        
        # initialise function callbacks
        self.tweetInspectors = []
        
        # if the run user has been specified, then find the access key for the user
        if run_as_user:
            accesskey_data = OAuthAccessKey.findByUserName(run_as_user)
            
            # if we have found some data, then update the access key
            if accesskey_data:
                self._accessKey = accesskey_data.accessKeyEncoded
                
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
            
        # if we don't have an access key we can't do anything
        if (self._accessKey is None):
            logging.warning("No access key set, suspect we have don't have a validation access key for %s", self._runAsUser)
            fnresult = True
            
        # reset the processed count
        self.processedCount = 0 
               
        # if we haven't run out of time then carry on
        if (not fnresult):
            # get the rule instance
            rule = twawlermodel.TwawlRule.findOrCreate(self.ruleName)
            
            # create the twitter search request
            search_request = twitter.newRequest(self.searchType, twitter_config = self._twitterConfig)
            search_request.accessToken = self._accessKey
            search_request.highTweetId = rule.highTweetId
            search_request.nextPage = self.nextRequest
            search_request.searchQuery = self.searchFor
            search_request.language = "en"
            
            logging.debug("High tweet id is %s", search_request.highTweetId)
            
            # make the request
            search_request.execute(self.processTweet)
            
            # if the request was not successful, return that we have finished immediately
            if not search_request.successful:
                return True
            
            # save the next page results, for if we get another shot
            self.nextRequest = search_request.nextPage
            
            # update the function result, based on the success of our search
            foundTweets = (search_request.nextPage is not None) or (self.highTweetId > search_request.highTweetId)
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