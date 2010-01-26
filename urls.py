from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url('^gaetools/rules/admin$', 'gaetools.views.twawl_admin'),
)