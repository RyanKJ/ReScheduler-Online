from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User


class Employee(models.Model):
    """Representation of an employee."""
    user = models.ForeignKey(User)

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
        
        return start_str + " - " + end_str
        
        
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
    #2) Add time interval for timepicker option for user
    #3) Add last calendar loaded state
    #4) Limit amount of employees displayable in eligable list option
    #5) Add lunch subtraction length of hours per 8 hour shift?
    #6) Display costs disable/enable option
    #7) Add overtime multiplier option
    
    overtime = models.IntegerField('overtime')
    workweek_weekday_start = models.IntegerField('weekday', default=0)
    workweek_time_start = models.TimeField('start time')
    display_am_pm = models.BooleanField()
    display_minutes = models.BooleanField()
    