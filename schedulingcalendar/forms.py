from django import forms

TIME_FORMATS = ['%I:%M %p']

class CalendarForm(forms.Form):
    department = forms.IntegerField(label='Department')
    year = forms.IntegerField(label='Year', min_value=1900, max_value=9999)
    month = forms.IntegerField(label='Month', min_value=0, max_value=13)
    
    
    
class AddScheduleForm(forms.Form):
    department = forms.IntegerField(label='Department')
    date = forms.DateField(label='Date')
    
    start_time =  forms.TimeField(label='Start Time',
                                        input_formats=TIME_FORMATS)
    end_time = forms.TimeField(label='End Time',
                                       input_formats=TIME_FORMATS)
                                                              
    hide_start = forms.BooleanField(label="Hide Start")
    hide_end = forms.BooleanField(label="Hide End")
    