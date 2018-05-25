"""
Original custom timezone aware time field found at: 
https://stackoverflow.com/questions/19780082/how-to-make-timefield-timezone-aware 

Original multiple integer field found at: 
https://stackoverflow.com/questions/29303902/django-form-with-list-of-integers
"""

from django import forms
from django.forms.fields import TimeField
from django.forms.utils import from_current_timezone, to_current_timezone
from django.utils import timezone
from datetime import datetime
import pytz


class TzAwareTimeField(TimeField):
    """Time field for django forms that preserves timezone information."""
    def prepare_value(self, value):
        if isinstance(value, datetime):
            value = value.time()
        return super(TzAwareTimeField, self).prepare_value(value)

    def clean(self, value):
        value = super(TzAwareTimeField, self).to_python(value)
        dt = timezone.now()
        dt = dt.replace(hour=value.hour, minute=value.minute,
                        second=value.second, microsecond=value.microsecond)
        return dt
        
        
class MultipleValueWidget(forms.TextInput):
    def value_from_datadict(self, data, files, name):
        return data.getlist(name + '[]')


class MultipleValueField(forms.Field):
    widget = MultipleValueWidget
    
        
def clean_int(x):
    try:
        return int(x)
    except ValueError:
        raise ValidationError("Cannot convert to integer: {}".format(repr(x)))
        
        
class MultipleIntField(MultipleValueField):
    def clean(self, value):
        return [clean_int(x) for x in value]
