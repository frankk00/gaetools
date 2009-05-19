# File: cachehelper.py
# This file is used to wrap some helper functions around the GAE caching methods
# 
# Section: Version History
# 19/05/2009 (DJO) - Created File

def createCacheKey(keyPrefix, *keyNames):
    """
    This function is simply used to generate a composite cache key given a number of string parameters.
    I have a gut feeling there is probably a much better way to do this, probably something like a string
    join method or something
    """
    fnresult= keyPrefix
    
    for keyName in keyNames:
        fnresult += "_" + keyName
        
    return fnresult
