from __future__ import unicode_literals
from django.db import models


class Employee(models.Model):

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

    name = models.CharField(max_length=100)
    members = models.ManyToManyField(Employee, through='DepartmentMembership')
    
    def __str__(self):             
        return self.name
        
        
class DepartmentMembership(models.Model):

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    # Integer used to determine if this is a primary (0th tier) or secondary
    # department for the employee (1st, 2nd, ... tier)
    priority = models.IntegerField('Department priority for employee', default=0)
    seniority = models.IntegerField('seniority', null=True, default=0)
    

class Schedule(models.Model):
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
    
    start_datetime = models.DateTimeField('start datetime')
    end_datetime = models.DateTimeField('end datetime')
    
    employee = models.ForeignKey(Employee)
    
    
class RepeatUnavailability(models.Model):
    start_time = models.TimeField('start time')
    end_time = models.TimeField('end time')
    # Weekday starts on Monday, so Monday = 0, Tuesday = 1, etc.
    weekday = models.IntegerField('weekday')
    
    employee = models.ForeignKey(Employee)
    
    
class MonthlyRevenue(models.Model):

    monthly_total = models.IntegerField('monthly total revenue')
    month_year = models.DateField('month and year')
    
    
class BusinessData(models.Model):
    """Collection of misc. business data, like overtime."""
    overtime = models.IntegerField('overtime')
    workweek_weekday_start = models.IntegerField('weekday', default=0)
    
    
    def check_for_overtime(self, hours):
        if hours > overtime:
            return True
        else:
            return False