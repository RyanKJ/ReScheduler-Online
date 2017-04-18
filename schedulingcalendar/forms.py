from django import forms
from datetime import datetime
from .models import Department

TIME_FORMATS = ['%I:%M %p']
MONTH_CHOICES = ((1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                 (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                 (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'))


class CalendarForm(forms.Form):

    def __init__(self, user, *args, **kwargs):
        super(CalendarForm, self).__init__(*args, **kwargs)
        
        # TODO: Add edge case where user has 0 departments
        dep_choices = get_department_tuple(user)
        year_choices = self.get_year_choices()
        
        self.fields['department'].widget.choices = dep_choices
        self.fields['year'].widget.choices = year_choices
        
        
    def get_year_choices(self):
        now = datetime.now()
        current_year = now.year
        year_choices = get_years_tuple(current_year, 5, 2)
        
        return year_choices
        

    department = forms.IntegerField(label='Department', widget=forms.Select(),
                                    min_value=0, max_value=1000)
    
    month = forms.IntegerField(label='Month', 
                               widget=forms.Select(choices=MONTH_CHOICES), 
                               min_value=0, max_value=13)
                               
    year = forms.IntegerField(label='Year', widget=forms.Select(), 
                              min_value=1900, max_value=9999)
                     
                   
class AddScheduleForm(forms.Form):
    # TODO Use SeperateDateTimeField?                        
    date_attrs = {'id': 'add-date', 'value': '', 'name': 'date'}
    add_date = forms.DateField(widget=forms.HiddenInput(attrs=date_attrs))
    
    dep_attrs = {'id': 'new-schedule-dep', 'value': '', 'name': 'department'}
    department = forms.IntegerField(widget=forms.HiddenInput(attrs=dep_attrs),
                                    min_value=0, max_value=1000)
    
    start_time_attrs = {'id': 'start-timepicker', 'name': 'start-timepicker'}
    start_time =  forms.TimeField(label='Start Time',
                                  widget=forms.TextInput(attrs=start_time_attrs),
                                  input_formats=TIME_FORMATS)
                                  
    hide_start_attrs = {'id': 'start-checkbox', 'name': 'hide-start', 'value': False}
    hide_start = forms.BooleanField(label="", 
                                    required=False,
                                    widget=forms.CheckboxInput(attrs=hide_start_attrs))
                                  
    end_time_attrs = {'id': 'end-timepicker', 'name': 'end-timepicker'}                      
    end_time = forms.TimeField(label='End Time',
                               widget=forms.TextInput(attrs=end_time_attrs),
                               input_formats=TIME_FORMATS)
                                                
    hide_end_attrs = {'id': 'end-checkbox', 'name': 'hide-end', 'value': False}
    hide_end = forms.BooleanField(label="", 
                                  required=False,
                                  widget=forms.CheckboxInput(attrs=hide_end_attrs))
    
    
def get_department_tuple(logged_user):
    departments = Department.objects.filter(user=logged_user).only('id', 'name')
    dep_choices = [(dep.id, dep.name) for dep in departments]
        
    return tuple(dep_choices)
    
    
def get_years_tuple(curr_year, n, m):
    """Return a tuple of strings representing years.
    
    Args:
        curr_year: string representation of present year
        n: number of years after present year desired to be in tuple
        m: number of years before year desired to be in tuple
    Returns:
        A tuple representing years spanning a length determined by the passed
        in arguments.
    """
        
    year_list = []
    start_year = int(curr_year) - m
    
    for i in range(start_year, start_year + n + m):
        year = str(i)
        year_list.append((year, year))
           
    return tuple(year_list)
    