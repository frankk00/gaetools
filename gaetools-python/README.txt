# GAE Tools Library
# Damon Oehlman - http://twitter.com/DamonOehlman
# Conceptual Advantage - http://conceptualadvantage.com/ 
#
# Licenced under the new BSD licence (see licence.txt)

The GAE tools library is designed to make the process of certain kinds of applications
even more enjoyable in the Google AppEngine.

Currently the functionality of the library includes:

*SlicedTasks* 
Functionality to enable effective use of the GAE cron jobs to perform background processing. 
This is really effective if you have a message queue or something you want to process.

*Twitter "Twawler"*
A library that wraps the twitter search API.  It's very rudimentary at this stage but will be extended in the
future.  Additionally oauth authentication has been implemented, but there are some tricks to using it...

*CacheHelper*
Doesn't do a whole lot at the moment.

== Dependencies ==
This library includes the following libraries as functionality within gaetools depends on it:

oauth python library (licensed under Apache 2.0) 
http://code.google.com/p/oauth/