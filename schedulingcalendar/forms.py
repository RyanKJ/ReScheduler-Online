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
        
        dep_choices = self.get_department_choices(user)
        year_choices = self.get_year_choices()
        
        self.fields['department'].widget.choices = dep_choices
        self.fields['year'].widget.choices = year_choices
        
     
    def get_department_choices(self, logged_user):
        # TODO: Add edge case where user has 0 departments
        departments = Department.objects.filter(user=logged_user).only('id', 'name')
        dep_choices = [(dep.id, dep.name) for dep in departments]
        
        return tuple(dep_choices)
        
        
    def get_year_choices(self):
        now = datetime.now()
        current_year = now.year
        year_choices = get_year_choices(current_year, 5, 2)
        
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
    department = forms.IntegerField(label='Department', widget=forms.Select(),
                                    min_value=0, max_value=1000)
    date = forms.DateField(label='Date')
    
    start_time =  forms.TimeField(label='Start Time',
                                        input_formats=TIME_FORMATS)
    end_time = forms.TimeField(label='End Time',
                                       input_formats=TIME_FORMATS)
                                                              
    hide_start = forms.BooleanField(label="Hide Start")
    hide_end = forms.BooleanField(label="Hide End")
    
    
def get_year_choices(curr_year, n, m):
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
    