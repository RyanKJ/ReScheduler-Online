from django import template

register = template.Library()

WEEKDAYS = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 
            4: 'Friday', 5: 'Saturday', 6: 'Sunday'}

            
@register.filter
def int_to_weekday(value):
    """Convert int representation of weekday to full string word.
    
    Weekday is considered to start on Monday, so if weekday=0 --> "Monday"
    """
    
    return WEEKDAYS[value]