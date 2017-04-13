from django import forms

TIME_FORMATS = ['%I:%M %p']
MONTH_CHOICES = ((1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                 (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                 (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'))


class CalendarForm(forms.Form):

    def __init__(self, dep_choices, year_choices, *args, **kwargs):
        super(CalendarForm, self).__init__(*args, **kwargs)
        self.fields['department'].choices = dep_choices
        self.fields['year'].choices = year_choices

    department = forms.IntegerField(label='Department', widget=forms.Select())
    
    month = forms.IntegerField(label='Month', 
                               widget=forms.Select(choices=MONTH_CHOICES), 
                               min_value=0, max_value=13)
                               
    year = forms.IntegerField(label='Year', widget=forms.Select(), 
                              min_value=1900, max_value=9999)
                     
                   
class AddScheduleForm(forms.Form):
    # TODO Use SeperateDateTimeField?
    department = forms.IntegerField(label='Department')
    date = forms.DateField(label='Date')
    
    start_time =  forms.TimeField(label='Start Time',
                                        input_formats=TIME_FORMATS)
    end_time = forms.TimeField(label='End Time',
                                       input_formats=TIME_FORMATS)
                                                              
    hide_start = forms.BooleanField(label="Hide Start")
    hide_end = forms.BooleanField(label="Hide End")
    