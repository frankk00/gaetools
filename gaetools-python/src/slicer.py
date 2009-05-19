# File: gaetools.py
# This module contains a collection of classes that are useful in operating with the GAE
# 
# Section: Version History
# 14/05/2009 (DJO) - Created File

# import standard libraries
import string
import logging
import datetime

# define the requeue interval - we really don't want to queue up an excess of events...
DEFAULT_MAX_INTERVAL = datetime.timedelta(seconds = 25)
DEFAULT_WRITECACHE_INTERVAL = 600

class SlicedTask:
    """
    The sliced task is used to define standard behaviour for a task that has to execute within a 
    certain time limit.  This is true for cron jobs on the GAE platform presently.  Potentially, 
    this has a lot of data to get through but this can assist in achieving that by slicing the data
    over time
    """    
    def __init__(self, maxInterval = DEFAULT_MAX_INTERVAL):
        """
        Initialise the new Sliced Task object
        """
        self.sliceTime = maxInterval
        self.taskComplete = False
        self.writeCacheInterval = DEFAULT_WRITECACHE_INTERVAL
        
    def getTimeRemaining(self):
        """
        This method is used to get the amount of time remaining in this execution slice
        """
        
        return self.startTime + self.sliceTime - datetime.datetime.utcnow() 
    
    def run(self, sliceAction):
        """
        This method is used to run the task, the method keeps a check on the time the task started and makes
        sure the task is completed with the maximum slice time - which ideally should be a couple of seconds
        less than the maximum time allowed for a webrequest
        """
                                                        
        # get the current time
        self.startTime = datetime.datetime.utcnow()
        
        try:
            # prepare the task to run
            self.setup()
            
            # while we are still under the required time, continue to execute
            while (not self.taskComplete) and (self.startTime + self.sliceTime > datetime.datetime.utcnow()):
                self.taskComplete = self.runTask(sliceAction)
        finally:
            # tear down the task
            self.tearDown()
            
            # log that the task was completed successfully
            logging.debug("task completed successfully")
            
    def runTask(self, sliceAction):
        """
        This method is used to do the actual work in descendant classes
        """
        logging.debug("running a background sliced task, %s seconds remaining", self.getTimeRemaining())
        
        # return true to tell the outer method that we had nothing to do
        return True
    
    def setup(self):
        """
        This method is used to prepare the task for running, in this section we will prepare any objects
        that could be used in the runTask method but don't want to spend the cost of creating those objects within
        that context.
        """
        
        logging.debug("task setup initiated")
        
        
    
    def tearDown(self):
        """
        This method is used to clean up anything that might have been created in the setup method of the slicedtask 
        """
        
        logging.debug("tearing down task")