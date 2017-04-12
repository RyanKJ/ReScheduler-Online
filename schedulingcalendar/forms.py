from django import forms

TIME_FORMATS = ['%I:%M %p']

class CalendarForm(forms.Form):
    department = forms.IntegerField(label='Department', max_length=60)
    year = forms.IntegerField(label='Year', max_length=4)
    month = forms.IntegerField(label='Month', max_length=2)
    
    
class AddScheduleForm(forms.Form):
    department = forms.IntegerField(label='Department', max_length=60)
    date = forms.DateField(label='Date')
    
    start-timepicker =  forms.TimeField(label='Start Time',
                                        input_formats=TIME_FORMATS)
    end-timepicker = forms.TimeField(label='End Time',
                                       input_formats=TIME_FORMATS)
                                       
                                       
    hide-start = forms.BooleanField(label="Hide Start")
    hide-end = forms.BooleanField(label="Hide End")
    