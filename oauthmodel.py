"""
File:   oauthmodel.py
This file is used to persist oauth access tokens for later user

Section:    Version History
23/01/2010 (DJO) - Created File
"""

# import standard libraries
import datetime
import logging

# import appengine libraries
from google.appengine.ext import db

class OAuthAccessKey(db.Model):
    """
    This class is used to facilitate persistence for OAuth
    """
    
    partnerId = db.StringProperty(required = True)
    userId = db.IntegerProperty(required = False)
    userName = db.StringProperty(required = False)
    requestKey = db.StringProperty(required = False)
    requestKeyEncoded = db.StringProperty(required = False)
    accessKeyEncoded = db.StringProperty(required = False)
    createDate = db.DateTimeProperty(required = True, auto_now_add = True)
    
    @staticmethod
    def findByRequestKey(key):
        """
        This static method is used to find a user by the request key
        """
        
        # initialise the query
        query = OAuthAccessKey.gql("WHERE requestKey = :key", key=key)
        
        # return the query result
        return query.get()
        
    @staticmethod
    def findByUserName(username):
        """
        This method is used to find the access key by the specified username, we
        will return the latest one (hopefully it's valid)
        """
        
        # initialise the query
        query = OAuthAccessKey.gql("WHERE userName = :name ORDER BY createDate DESC", name=username)
        
        # return the query result
        return query.get()
        
    @staticmethod
    def findOrCreate(key, partnerId = 'Unspecified', allowCreate = True):
        """
        This static method is used to find or create the required user that will be used to 
        store the oauth request and access keys
        """
        
        # convert the user id to lower case
        fnresult = OAuthAccessKey.findByRequestKey(key)
        
        # if we couldn't find the user then create him
        if allowCreate and (fnresult == None):
            fnresult = OAuthAccessKey(requestKey = key, partnerId = partnerId)
            
        return fnresult