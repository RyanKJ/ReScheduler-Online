from django import template
from django.contrib.auth.models import Group 
import datetime

register = template.Library()

WEEKDAYS = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 
            4: 'Friday', 5: 'Saturday', 6: 'Sunday'}    
TIME_FORMAT = "%I:%M %p"

            
@register.filter
def int_to_weekday(value):
    """Convert int representation of weekday to full string word.
    
    Weekday is considered to start on Monday, so if weekday=0 --> "Monday"
    """
    
    return WEEKDAYS[value]
    
    
@register.filter
def datetime_to_time(value):
    """Convert python datetime to a formatted time value."""
    
    return value.strftime(TIME_FORMAT)
    
    
@register.filter(name='has_group') 
def has_group(user, group_name):
    """Checks if user is a manager user or not."""
    return user.groups.filter(name=group_name).exists()