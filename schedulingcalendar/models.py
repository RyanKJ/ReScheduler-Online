from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User
from datetime import datetime, time


class Employee(models.Model):
    """Representation of an employee profile and for schedule assignment."""
    user = models.ForeignKey(User, related_name='manager', null=True)
    employee_user = models.OneToOneField(User, on_delete=models.SET_NULL, 
                                         related_name='employee', 
                                         null=True, blank=True)

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField()
    employee_id = models.IntegerField('employee id')
    wage = models.FloatField('employee wage')
    desired_hours = models.IntegerField('desired weekly hours')
    # Benefits costs
    monthly_medical = models.IntegerField('monthly medical')
    workmans_comp = models.IntegerField('workmans comp')
    social_security = models.IntegerField('social security')

    
    def __str__(self):             
        return "%s %s" % (self.first_name, self.last_name)
           
        
class Department(models.Model):
    """Representation of business department."""
    user = models.ForeignKey(User)

    name = models.CharField(max_length=100)
    members = models.ManyToManyField(Employee, through='DepartmentMembership')
    
    def __str__(self):             
        return self.name
        
        
class DepartmentMembership(models.Model):
    """Representation of relationship between an employee and department."""
    user = models.ForeignKey(User)

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    # Integer used to determine if this is a primary (0th tier) or secondary
    # department for the employee (1st, 2nd, ... tier)
    priority = models.IntegerField('Department priority for employee', default=0)
    seniority = models.IntegerField('seniority', null=True, default=0)
    

class Schedule(models.Model):
    """Representation of a work schedule for a business."""
    user = models.ForeignKey(User)

    start_datetime = models.DateTimeField('start datetime')
    end_datetime = models.DateTimeField('end datetime')
    
    hide_start_time = models.BooleanField()
    hide_end_time = models.BooleanField()
    
    department = models.ForeignKey(Department)
    employee = models.ForeignKey(Employee, null=True)
    
    
    def __str__(self):
        start_str = self.start_datetime.strftime("%B %d, %I:%M %p")
        end_str = self.end_datetime.strftime("%I:%M %p")
        
        return "Department: " + self.department.name + " " + start_str + " - " + end_str
        
        
    # __gt__ and __lt__ are implemented for use in bisect
    def __gt__(self, other):
        """Comparison if end_datetime is greater than other schedule."""
        if not isinstance(other, Schedule):
            raise Exception("Schedules are only comparable to other Schedules, not to %s" % type(other))
        else:
            return self.end_datetime > other.end_datetime
            

    def __lt__(self, other):
        """Comparison if end_datetime is less than other schedule."""
        if not isinstance(other, Schedule):
            raise Exception("Schedules are only comparable to other Schedules, not to %s" % type(other))
        else:
            return self.end_datetime < other.end_datetime
        

class LiveCalendar(models.Model):
    """Representation of a collection of live schedules for given date/dep."""
    user = models.ForeignKey(User)
    
    date = models.DateField('Date', default=datetime.now().date())
    department = models.ForeignKey(Department)
    version = models.IntegerField('Version', default=1)
    active = models.BooleanField(default=True)
    
    def __str__(self):
        date_str = self.date.strftime("%B %d")
        
        
        return "Department: " + self.department.name + " " + date_str
    
    
class LiveSchedule(models.Model):
    """Copy of schedule used for displaying finished calendar to employees."""
    user = models.ForeignKey(User)
    schedule = models.OneToOneField(Schedule, on_delete=models.SET_NULL, null=True)
    calendar = models.ForeignKey(LiveCalendar)

    start_datetime = models.DateTimeField('start datetime')
    end_datetime = models.DateTimeField('end datetime')
    
    hide_start_time = models.BooleanField()
    hide_end_time = models.BooleanField()
    
    department = models.ForeignKey(Department)
    employee = models.ForeignKey(Employee)
    
        
class Vacation(models.Model):
    """Representation of a vacation block of time for employee absentee."""
    user = models.ForeignKey(User)
    
    start_datetime = models.DateTimeField('start datetime')
    end_datetime = models.DateTimeField('end datetime')
    
    employee = models.ForeignKey(Employee)
    
    
class Absence(models.Model):
    """Representation of an absent block of time for employee."""
    user = models.ForeignKey(User)
    
    start_datetime = models.DateTimeField('start datetime')
    end_datetime = models.DateTimeField('end datetime')
    
    employee = models.ForeignKey(Employee)    
    
    
class RepeatUnavailability(models.Model):
    """Representation of repeating unavailability for employee absentee."""
    user = models.ForeignKey(User)
    
    start_time = models.TimeField('start time')
    end_time = models.TimeField('end time')
    # Weekday starts on Monday, so Monday = 0, Tuesday = 1, etc.
    weekday = models.IntegerField('weekday')
    
    employee = models.ForeignKey(Employee)
    
    
class DesiredTime(models.Model):
    """Representation of repeating desired work time for employee."""
    user = models.ForeignKey(User)
    
    start_time = models.TimeField('start time')
    end_time = models.TimeField('end time')
    # Weekday starts on Monday, so Monday = 0, Tuesday = 1, etc.
    weekday = models.IntegerField('weekday')
    
    employee = models.ForeignKey(Employee)
    
    
class MonthlyRevenue(models.Model):
    """Representation of total revenue for a business for given month & year."""
    user = models.ForeignKey(User)

    monthly_total = models.IntegerField('monthly total revenue')
    month_year = models.DateField('month and year')
    
    
class BusinessData(models.Model):
    """Collection of misc. business data, like overtime."""
    user = models.ForeignKey(User)
    
    #TODO:
    #1) Add timezone of managing user
    #2) Add last calendar loaded state
    #3) Add time interval for timepicker option for user
    #4) Display costs disable/enable option
    #5) Limit amount of employees displayable in eligable list option
    #6) 24 hour time option
    #7) Count overlapping time or not?
    #8) Option to customize eligable sort?
    
    # Business Settings
    overtime = models.IntegerField('Overtime In Hours', default=40)
    overtime_multiplier = models.FloatField('Overtime Multiplier', default=1.5)
    workweek_weekday_start = models.IntegerField('weekday', default=0)
    workweek_time_start = models.TimeField('start time', time(0, 0, 0))
    min_time_for_break = models.FloatField('Minimum Schedule Duration In Hours For Break Eligability', 
                                           default=5)
    break_time_in_min = models.IntegerField('Average Break Length In Minutes Per Eligable Schedule', 
                                            default=30)
    # Calendar Display Settings
    display_am_pm = models.BooleanField(default=False)
    display_minutes = models.BooleanField(default=True)
    display_last_names = models.BooleanField(default=False)
    display_first_char_last_name = models.BooleanField(default=False)
    