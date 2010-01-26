"""
Module:     gaetools.django.views
This module is used to define views for the gaetools library for tighter integration
into django

Section:    Version History
21/01/2010 (DJO) - Created File
"""

from django.shortcuts import render_to_response
from forms import TwawlRuleForm
import logging

def twawl_admin(request):
    if request.POST:
        admin_form = TwawlRuleForm(request.POST)
        if admin_form.is_valid():
            admin_form.save()
            logging.info("posted and valid")
    else:
        admin_form = TwawlRuleForm()
    
    return render_to_response('genform.html', { 'form': admin_form })    