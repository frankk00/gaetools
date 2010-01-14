# File: proxy.py
# This file is used to define a content proxy that will enable GAE applications to screen-scrape other content
# into their GAE applications.  Please use this for good and not evil...
# 
# Section:  Version History
# 19/05/2009 (DJO) - Created File

# import standard libaries
import logging
import exceptions

# import gae supported 3rd party libraries
import yaml

# import the appengine libraries
from google.appengine.api import urlfetch
from google.appengine.api import memcache

# import other gaetools libraries
import cachehelper

# initialise constants
CONFKEY_MATCH = "match"
CONFKEY_BASEURL = "baseUrl"

# initialise defaults
DEFAULT_PROXY_CONFIG = "proxy"

class ProxyConfig:
    """
    The ProxyConfig class is used to read the configuration information from the conf directory
    """
    
    def __init__(self, config = DEFAULT_PROXY_CONFIG):
        """
        Default constructor for the TwitterConfig class
        """
        
        # initialise members
        self.configurations = []
        
        # load the configuration from the specified configuration
        self.load(config)
    
    def load(self, config = DEFAULT_PROXY_CONFIG):
        """
        Load the required config from the cache or configuration file if not available
        """
        
        # check to see if the config is currently cached
        self.configurations = memcache.get(cachehelper.createCacheKey("twitter-config", config))

        # if the dataMap is not cached, then load it from the yaml in the filesystem
        if self.configurations is None:           
            # open the required configuration file (using the conf directory)
            fHandle = open('conf/' + config + '.yaml')
            
            # now read the configuration information, and then close the file
            try:
                tmpConfigurations = yaml.load(fHandle)
                
                # validate the configuration
                validateConfig(tmpConfigurations)

                # save the datamap to the cache
                self.configurations = tmpConfigurations
                memcache.set(cachehelper.createCacheKey("twitter-config", config), self.configurations)
            finally:
                fHandle.close()    
                
    def validateConfig(self, config):
        """
        This method is used to check the specified configuration for any errors in the format
        """
        
        # log a warning if the config has no elements, it's not an error the proxy just won't do anything
        if (config is None) or (config.length == 0):
            logging.warn("The configuration is empty, the content proxy will behave similar to an inert gas")
        
        # iterate over the elements of the config and check for errors
        for configItem in config:
            # check the match is specified
            if CONFKEY_MATCH not in configItem:
                raise ProxyConfigException()
            
            # check the base url is specified
            if CONFKEY_BASEURL not in configItem:
                raise ProxyConfigException()
            
class ProxyConfigException(Exception):
    """
    The proxy configuration exception is used to flag when there is a problem with the proxy configuration.
    Kind of self explanatory really...
    """

class ContentProxy:
    """
    The ContentProxy class is used to bring content from a specific url and return the content to the display
    """
    
    def __init__(self, configName = DEFAULT_PROXY_CONFIG):
        """
        The ContentProxy class constructor.  The constructor is responsible for
        loading the specified proxy configuration and initialise member variables
        """
        
        # load the specified proxy configuration
        self.config = ProxyConfig(configName)
        
    def get(self, uri):
        """
        The get method is used to retrieve the specified url and return the content 
        """
        
        logging.debug("requested %s", uri)
        
        # iterate through the configurations and look for a match to the url
        for config in self.configurations:
            if config.
        
        return "Hello World!"
        
class CachingContentProxy(ContentProxy):
    """
    The CachingContentProxy extends the ContentProxy and adds functionality to implement caching on the retrieval
    process (which is pretty much mandatory).  Background processes are used to clear the cache where required to 
    instruct the proxy to refresh particular objects
    """
    
    def get(self, uri):
        """
        The get method is used to return the cached content for the specified uri
        """
        
        return ContentProxy.get(self, uri)
        