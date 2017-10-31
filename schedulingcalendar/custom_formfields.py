"""
Original custom timezone aware time field found at: 
https://stackoverflow.com/questions/19780082/how-to-make-timefield-timezone-aware 

By user:
https://stackoverflow.com/users/174709/josh
"""


from django.forms.fields import TimeField
from django.forms.utils import from_current_timezone, to_current_timezone
from django.utils import timezone
from datetime import datetime
import pytz


class TzAwareTimeField(TimeField):
    """Time field for django forms that preserves timezone information."""
    def prepare_value(self, value):
        if isinstance(value, datetime):
            value = to_current_timezone(value).time()
        return super(TzAwareTimeField, self).prepare_value(value)

    def clean(self, value):
        value = super(TzAwareTimeField, self).to_python(value)
        time_zone = timezone.get_default_timezone_name()
        dt = datetime.now()
        dt = pytz.timezone(time_zone).localize(dt)
        dt = dt.replace(hour=value.hour, minute=value.minute,
                        second=value.second, microsecond=value.microsecond)
        return dt