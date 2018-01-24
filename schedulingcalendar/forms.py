from django import forms
from datetime import datetime
from .models import (Employee, Department, DepartmentMembership, 
                     Vacation, Absence, RepeatUnavailability, DesiredTime, 
                     MonthlyRevenue, BusinessData, DayNoteHeader, DayNoteBody)
from custom_formfields import TzAwareTimeField

DATE_FORMAT = '%Y, %B'
DATE_FORMATS = [DATE_FORMAT]
TIME_FORMATS = ['%I:%M %p']
MONTH_CHOICES = ((1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                 (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                 (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'))
WEEKDAY_CHOICES = ((0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
                   (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), 
                   (6, 'Sunday'))                 
                 
                 
DATETIME_FORMAT = "%B %d, %Y at %I:%M %p"
DATETIME_FORMATS = [DATETIME_FORMAT]


class CalendarForm(forms.Form):
    """Form for user to select a calendar given year, month, & department."""
    
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
                              
                              
class LiveCalendarForm(forms.Form):
    """Form for user to select a calendar given year, month, & department.
    
    Different from CalendarForm in that employees have a boolean option to
    display only their schedules or all schedules for a given calendar.
    
    Also, departments are fetched from associated manager user for employee,
    as employees themselves are not 'owners' of any departments.
    """
    
    def __init__(self, user, *args, **kwargs):
        super(LiveCalendarForm, self).__init__(*args, **kwargs)
        
        # TODO: Add edge case where user has 0 departments
        dep_choices = get_department_tuple(user)
        year_choices = self.get_year_choices()
        
        self.fields['department'].widget.choices = dep_choices
        self.fields['year'].widget.choices = year_choices
        
        
    def get_year_choices(self):
        now = datetime.now()
        current_year = now.year
        year_choices = get_years_tuple(current_year, 2, 1)
        
        return year_choices
        

    department = forms.IntegerField(label='Department', widget=forms.Select(),
                                    min_value=0, max_value=1000)
    
    month = forms.IntegerField(label='Month', 
                               widget=forms.Select(choices=MONTH_CHOICES), 
                               min_value=0, max_value=13)
                               
    year = forms.IntegerField(label='Year', widget=forms.Select(), 
                              min_value=1900, max_value=9999)
                              
    employee_only = forms.BooleanField(label="", required=False,
                                       widget=forms.CheckboxInput())
                                       
                                       
class LiveCalendarManagerForm(forms.Form):
    """Form for manager to view a calendar given year, month, & department.
    
    The fields except version will have hidden widgets because the manager does 
    not edit the live calendar, but can view previous versions of that year and
    department.
    """
    def __init__(self, user, num_of_versions=1, *args, **kwargs): 
        super(LiveCalendarManagerForm, self).__init__(*args, **kwargs)
        
        # TODO: Add edge case where user has 0 departments
        dep_choices = get_department_tuple(user)
        year_choices = self.get_year_choices()
        live_cal_version_choices = self.get_version_choices(num_of_versions)
        
        self.fields['department'].widget.choices = dep_choices
        self.fields['year'].widget.choices = year_choices
        self.fields['version'].widget.choices = live_cal_version_choices
        
        
    def get_year_choices(self):
        now = datetime.now()
        current_year = now.year
        year_choices = get_years_tuple(current_year, 5, 2)
        
        return year_choices
        
        
    def get_version_choices(self, num_of_versions):
        """Create tuple of versions for select widget."""
        version_list = [] 
        
        for i in range(1, num_of_versions + 1):
            version = str(i)
            version_list.append((version, version))
               
        return tuple(version_list)
            

    department = forms.IntegerField(label='Department', widget=forms.HiddenInput(),
                                    min_value=0, max_value=1000)
    
    month = forms.IntegerField(label='Month', 
                               widget=forms.HiddenInput(), 
                               min_value=0, max_value=13)
                               
    year = forms.IntegerField(label='Year', widget=forms.HiddenInput(), 
                              min_value=1900, max_value=9999)
                              
    version = forms.IntegerField(label='Select Version', 
                                 widget=forms.Select(), 
                                 min_value=1, max_value=9999)
                                       
                              
                                                        
class PushLiveForm(forms.Form):
    """Form for making currently selected calendar live for employee query."""
    date_attrs = {'id': 'date', 'value': '', 'name': 'date'}
    date = forms.DateField(widget=forms.HiddenInput(attrs=date_attrs))
    
    dep_attrs = {'id': 'department', 'value': '', 'name': 'department'}
    department = forms.IntegerField(widget=forms.HiddenInput(attrs=dep_attrs),
                                    min_value=0, max_value=1000)
                                    
                                    
class SetActiveStateLiveCalForm(forms.Form):
    """Form for setting active/deactive state of a live calendar."""
    date_attrs = {'id': 'date', 'value': '', 'name': 'date'}
    date = forms.DateField(widget=forms.HiddenInput(attrs=date_attrs))
    
    dep_attrs = {'id': 'department', 'value': '', 'name': 'department'}
    department = forms.IntegerField(widget=forms.HiddenInput(attrs=dep_attrs),
                                    min_value=0, max_value=1000)
                                    
    active = forms.BooleanField(label="Set Active State", required=False,
                                widget=forms.CheckboxInput())
                                
                                
class ViewLiveCalendarForm(forms.Form):
    """Form for manager to view an existing and active live calendar."""
    date_attrs = {'id': 'view-live-date', 'value': '', 'name': 'date'}
    date = forms.DateField(widget=forms.HiddenInput(attrs=date_attrs))
    
    dep_attrs = {'id': 'view-live-department', 'value': '', 'name': 'department'}
    department = forms.IntegerField(widget=forms.HiddenInput(attrs=dep_attrs),
                                    min_value=0, max_value=1000)
                                    
                                    
class AddScheduleForm(forms.Form):
    """Form for user to create a new schedule."""

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
                
                
class DepartmentMembershipForm(forms.ModelForm):
    """Form for creating and editing department memberships."""                                                                               
    def __init__(self, user, *args, **kwargs):
        super(DepartmentMembershipForm, self).__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(user=user)
                                
                                
    class Meta:
        model = DepartmentMembership
        fields = ['department', 'priority', 'seniority']
                                  
                                  
class VacationForm(forms.ModelForm):
    """Form for creating and editing vacations."""
    start_datetime = forms.DateTimeField(widget=forms.DateTimeInput(format=DATETIME_FORMAT),
                                     input_formats=DATETIME_FORMATS)
    end_datetime = forms.DateTimeField(widget=forms.DateTimeInput(format=DATETIME_FORMAT),
                                   input_formats=DATETIME_FORMATS)

    class Meta:
        model = Vacation
        fields = ['start_datetime', 'end_datetime']
        
        
class AbsentForm(forms.ModelForm):
    """Form for creating and editing vacations."""
    start_datetime = forms.DateTimeField(widget=forms.DateTimeInput(format=DATETIME_FORMAT),
                                     input_formats=DATETIME_FORMATS)
    end_datetime = forms.DateTimeField(widget=forms.DateTimeInput(format=DATETIME_FORMAT),
                                   input_formats=DATETIME_FORMATS)

    class Meta:
        model = Absence
        fields = ['start_datetime', 'end_datetime']
        
        
class RepeatUnavailabilityForm(forms.ModelForm):
    """Form for creating and editing repeating unavailabilities."""   
    weekday = forms.IntegerField(label='Weekday', 
                                 widget=forms.Select(choices=WEEKDAY_CHOICES), 
                                 min_value=0, max_value=6)
    start_time = TzAwareTimeField(label='Start Time', 
                                  input_formats=TIME_FORMATS,
                                  widget=forms.TimeInput(format='%I:%M %p'))                           
    end_time = TzAwareTimeField(label='End Time', 
                                input_formats=TIME_FORMATS,
                                widget=forms.TimeInput(format='%I:%M %p'))                            

                                
    class Meta:
        model = RepeatUnavailability
        fields = ['start_time', 'end_time', 'weekday']
        
        
class DesiredTimeForm(forms.ModelForm):
    """Form for creating and editing desired times."""   
    weekday = forms.IntegerField(label='Weekday', 
                               widget=forms.Select(choices=WEEKDAY_CHOICES), 
                               min_value=0, max_value=6)
    start_time = TzAwareTimeField(label='Start Time', 
                                         input_formats=TIME_FORMATS,
                                         widget=forms.TimeInput(format='%I:%M %p'))                           
    end_time = TzAwareTimeField(label='End Time', 
                                input_formats=TIME_FORMATS,
                                widget=forms.TimeInput(format='%I:%M %p'))                            

                                
    class Meta:
        model = DesiredTime
        fields = ['start_time', 'end_time', 'weekday']
        
        
class BusinessDataForm(forms.ModelForm):
    """Form for editing business data."""   
    workweek_weekday_start = forms.IntegerField(label='Workweek Start Day', 
                                                widget=forms.Select(choices=WEEKDAY_CHOICES), 
                                                min_value=0, max_value=6)
    workweek_time_start =  forms.TimeField(label='Workweek Start Time', 
                                           input_formats=TIME_FORMATS,
                                           widget=forms.TimeInput(format='%I:%M %p'))
    display_am_pm = forms.BooleanField(label="", required=False,
                                       widget=forms.CheckboxInput())
    display_minutes = forms.BooleanField(label="", required=False,
                                         widget=forms.CheckboxInput())
    display_nonzero_minutes = forms.BooleanField(label="", required=False,
                                                 widget=forms.CheckboxInput())
    display_last_names = forms.BooleanField(label="", required=False,
                                            widget=forms.CheckboxInput())                                     
    display_first_char_last_name = forms.BooleanField(label="", required=False,
                                                      widget=forms.CheckboxInput())
    sort_by_names = forms.BooleanField(label="", required=False,
                                       widget=forms.CheckboxInput())    
    unique_row_per_employee = forms.BooleanField(label="", required=False,
                                                 widget=forms.CheckboxInput())                                     

    class Meta:
        model = BusinessData
        fields = ['overtime', 'overtime_multiplier', 'workweek_weekday_start', 
                  'workweek_time_start', 'min_time_for_break', 'break_time_in_min', 
                  'display_am_pm', 'display_minutes', 'display_nonzero_minutes', 
                  'display_last_names', 'display_first_char_last_name', 
                  'desired_hours_overshoot_alert', 'sort_by_names',
                  'unique_row_per_employee']
        
        
class MonthlyRevenueForm(forms.ModelForm):
    """Form for creating and editing monthly revenues."""                                                     
    month_year =  forms.DateField(label='Year And Month',
                                  widget=forms.DateInput(format=DATE_FORMAT),
                                  input_formats=DATE_FORMATS)
                                
    class Meta:
        model = MonthlyRevenue
        fields = ['monthly_total', 'month_year']
        
        
class DayNoteHeaderForm(forms.ModelForm):
    """Form for creating and editing day note headers."""                                                    
                                
    class Meta:
        model = DayNoteHeader
        fields = ['date', 'header_text']
        
        
class DayNoteBodyForm(forms.ModelForm):
    """Form for creating and editing day note's for a day body."""                                                    
                                
    class Meta:
        model = DayNoteBody
        fields = ['date', 'body_text']
        
        
class ScheduleNoteForm(forms.Form):
    schedule_pk = forms.IntegerField(label='schedule id')
    schedule_text = forms.CharField(label='Note', max_length=280)
    
    
def get_department_tuple(logged_user):
    """Return a tuple of strings departments
    
    Args:
        logged_user: current logged in user via django authentication system.
    Returns:
        A tuple containing all departments of user where each element is a 
        tuple containing department id and name.
    """
    
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
    