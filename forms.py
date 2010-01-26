"""
Module: gaetools.django.forms
Defines a number of form classes that are used to manage model instances

Section:    Version History
21/01/2010 (DJO) - Created File
"""

from django.forms import ModelForm
from gaetools.twawlermodel import TwawlRule

class TwawlRuleForm(ModelForm):
    class Meta:
        model = TwawlRule        