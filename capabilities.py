# Module:   gaetools.capabilities
# This module wraps some of the capabilties functionality of the google appengine so you can proactively
# determine what services are available in the appengine stack.  This module has largely been built based on the 
# announcement that appeared in the google appengine downtime notify group advising that developers should monitor
# for exceptions in their applications to gracefully handle errors - not ideal in my opinion (see link below)
#
# http://groups.google.com/group/google-appengine-downtime-notify/browse_thread/thread/92ed4ae83f5509a0
# 
# The helper in this module uses the little used capabilies api to test whether or not certain service are available.
# Obviously, you use this helper at your own risk - as it is dependant on text strings for services remaining the same
# over time (although I will attempt to keep these up to date).
#
# Additionally, I would point out that someone with more python experience can probably implement the below
# code in a more graceful way.
# 
# Section: Version History
# 09/06/2009 (DJO) - Created File

import logging
from google.appengine.base.capabilities_pb import CapabilityConfigList, CapabilityConfig 
from google.appengine.api.capabilities import CapabilitySet
from google.appengine.api import apiproxy_stub_map

# define constants
KEY_TITLE = 'title'
KEY_PACKAGE = 'package'
KEY_CAPABILITIES = 'capabilities'

# define some defaults
DEFAULT_CAPABILITY_CHECKS = [
    {'title': 'db-read', 'package': 'datastore_v3', 'capabilities': ['read']},
    {'title': 'db-write', 'package': 'datastore_v3', 'capabilities': ['write']},
]

class CapabilityChecker:
    """
    The capability checker does what it advertises on the packet.  
    """ 
    
    def __init__(self):
        """
        Initialise the instance of the capabilty checker, set the states to the default states
        """
        
        # initialise members
        self.availability = [] 
        
    def getCapabilities(self):
        """
        This method attempts to get the capabilities from the current appengine instance by initiating 
        a call to the CapabilityConfigList protocol message
        """
        
        # initialise the request
        resp = CapabilityConfigList()
        
        # make the call
        apiproxy_stub_map.MakeSyncCall('capability_service', 'getCapabilities', resp, resp)
        
        # iterate over the configs found
        for config in resp.config_list():
            logging.debug("has capability: %s", config)
    
    def run(self, checks = DEFAULT_CAPABILITY_CHECKS):
        """
        This method is used to run the specified set of tests
        """
        
        # reset the availability list
        self.availability = []
        
        # iterate over the list of checks and execute them
        for check_instance in checks:
            # ensure that we have a title 
            if (not KEY_TITLE in check_instance) or (not KEY_PACKAGE in check_instance):
                logging.warning("Invalid check defined: %s", check_instance)
                continue
            
            logging.debug("Running the %s check", check_instance[KEY_TITLE])
            
            # initialise determine the capabilities we are looking for
            caps = []
            if KEY_CAPABILITIES in check_instance:
                caps = check_instance[KEY_CAPABILITIES]
                
            # create the capability set instance
            capset = CapabilitySet(check_instance[KEY_PACKAGE], caps, ['*'])
            
            # create the service availability record
            service_avail = {
                'title': check_instance[KEY_TITLE],
                
                # determine whether the service is available now
                'avail_now': capset.is_enabled(),

                # determine whether the service will still be available in one hour
                'avail_hour': capset.will_remain_enabled_for(3600),
                
                # update the availability array
                'avail_day': capset.will_remain_enabled_for(86400),
            }
            
            # log the results
            logging.debug("Completed availability check, results below\n%s", service_avail)
            
            # add the availability to the service list
            self.availability += service_avail