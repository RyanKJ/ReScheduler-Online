from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import datetime, date, time



class UserProfile(models.Model):
    """Meta-data and additional info for users"""
    user = models.OneToOneField(User, db_index=True, on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)


@receiver(post_save, sender=User)
def update_user_profile(sender, instance, created, **kwargs):
    """Update or create user profile associated with user."""
    if created:
        user_profile = UserProfile.objects.create(user=instance)
        user_profile.save()
    else:
        instance.userprofile.save()


class Employee(models.Model):
    """Representation of an employee profile and for schedule assignment."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE, related_name='manager', null=True)
    employee_user = models.OneToOneField(User, db_index=True, on_delete=models.SET_NULL,
                                         related_name='employee',
                                         null=True, blank=True)

    first_name = models.CharField(max_length=80, default="")
    last_name = models.CharField(max_length=80, default="")
    email = models.EmailField(null=True, blank=True, default="")
    phone_number = models.CharField('phone number', null=True, blank=True, max_length=17, default="")
    employee_id = models.IntegerField('employee id', default=0)
    wage = models.FloatField('employee wage', default=0)
    desired_hours = models.IntegerField('desired weekly hours', default=30)
    
    # Benefits costs
    monthly_medical = models.FloatField('Monthly medical in dollars per month', default=0)
    workmans_comp = models.FloatField('workmans comp', default=0)
    social_security = models.FloatField('Social security percentage', default=7.5)
    
    # Calendar display settings
    override_list_view = models.BooleanField(default=True)
    see_only_my_schedules = models.BooleanField(default=False)
    see_all_departments = models.BooleanField(default=False)
    
    # Break time settings
    min_time_for_break = models.FloatField('Minimum Schedule Duration In Hours For Break Eligability',
                                           default=5)
    break_time_in_min = models.IntegerField('Average Break Length In Minutes Per Eligable Schedule',
                                            default=30)


    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)
        
        
@receiver(post_save, sender=Employee)
def update_employee_user(sender, instance, created, **kwargs):
    """Set email of employee user to be same as email of employee profile."""
    if instance.employee_user:
        employee_user = instance.employee_user
        employee_user.email = instance.email
        employee_user.save()
   

@receiver(post_delete, sender=Employee)
def delete_employee_user(sender, instance, **kwargs):
    """Delete employee user associated with deleted employee."""
    if instance.employee_user:
        instance.employee_user.delete()


class Department(models.Model):
    """Representation of business department."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    name = models.CharField(max_length=100, default="")
    members = models.ManyToManyField(Employee, through='DepartmentMembership')

    def __str__(self):
        return self.name


class DepartmentMembership(models.Model):
    """Representation of relationship between an employee and department."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    def limit_dep_choices():
        """Limit departments for membership to user that owns employee."""
        return Department.objects.filter(user=self.user)

    employee = models.ForeignKey(Employee, db_index=True, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, db_index=True,
                                   on_delete=models.CASCADE)
    # Integer used to determine if this is a primary (0th tier) or secondary
    # department for the employee (1st, 2nd, ... tier)
    priority = models.IntegerField('Department priority for employee', default=0)
    seniority = models.IntegerField('seniority', null=True, default=0)

    def __str__(self):
        return "Dep mem for: " + self.employee.__str__() + " in dep " + self.department.name


class Schedule(models.Model):
    """Representation of a work schedule for a business."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_datetime = models.DateTimeField('start datetime', db_index=True, default=timezone.now)
    end_datetime = models.DateTimeField('end datetime', db_index=True, default=timezone.now)

    hide_start_time = models.BooleanField(default=False)
    hide_end_time = models.BooleanField(default=False)

    schedule_note = models.CharField(default="", blank=True, max_length=280)

    department = models.ForeignKey(Department, db_index=True)
    employee = models.ForeignKey(Employee, db_index=True, null=True)


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
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    date = models.DateField('Date', db_index=True, default=date.today)
    department = models.ForeignKey(Department, db_index=True)
    version = models.IntegerField('Version', db_index=True, default=1)
    all_employee_view = models.BooleanField(default=True)

    # View right model fields
    all_employee_view = models.BooleanField(default=True)
    department_view_rights = models.ManyToManyField(Department, db_index=True,
                                                    related_name='department_view_rights',
                                                    through='LiveCalendarDepartmentViewRights')
    employee_view_rights = models.ManyToManyField(Employee, db_index=True,
                                                  through='LiveCalendarEmployeeViewRights')


    def __str__(self):
        date_str = self.date.strftime("%B %d")
        return "Department: " + self.department.name + " " + date_str
        
        
class LiveCalendarVersionTimestamp(models.Model):
    """Timestamp of a LiveCalendar's version upon publishing."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    calendar = models.ForeignKey(LiveCalendar, db_index=True)
    version = models.IntegerField('Version', db_index=True, default=1)
    timestamp = models.DateTimeField('Timestamp', default=timezone.now)
    
    
    def __str__(self):
        return "Live Cal Timestamp: " + str(self.version) + " " + self.timestamp.isoformat()


class LiveSchedule(models.Model):
    """Copy of schedule used for displaying finished calendar to employees."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, db_index=True, on_delete=models.SET_NULL, null=True)
    calendar = models.ForeignKey(LiveCalendar, db_index=True)
    version = models.IntegerField('Version', db_index=True, default=1)

    start_datetime = models.DateTimeField('start datetime', default=timezone.now)
    end_datetime = models.DateTimeField('end datetime', default=timezone.now)

    hide_start_time = models.BooleanField(default=False)
    hide_end_time = models.BooleanField(default=False)

    schedule_note = models.CharField(default="", blank=True, max_length=280)

    department = models.ForeignKey(Department, db_index=True)
    employee = models.ForeignKey(Employee, db_index=True)


    def __str__(self):
        start_str = self.start_datetime.strftime("%B %d, %I:%M %p")
        end_str = self.end_datetime.strftime("%I:%M %p")

        return "Department " + self.department.name + " on " + start_str + " - " + end_str


class LiveCalendarDepartmentViewRights(models.Model):
    """Join table of LiveCalendar & departments that list what
    departments can view the live calendar.
    """

    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    live_calendar = models.ForeignKey(LiveCalendar, db_index=True, on_delete=models.CASCADE)
    department_view_rights = models.ForeignKey(Department, db_index=True, on_delete=models.CASCADE)


    def __str__(self):
        return "Department Pks " + self.department_view_rights + " for live calendar " + self.live_calendar


class LiveCalendarEmployeeViewRights(models.Model):
    """Join table of LiveCalendar & employees that list which
    employees can view the live calendar.
    """

    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    live_calendar = models.ForeignKey(LiveCalendar, db_index=True, on_delete=models.CASCADE)
    employee_view_rights = models.ForeignKey(Employee, db_index=True, on_delete=models.CASCADE)


    def __str__(self):
        return "Employee Pks " + self.employee_view_rights + " for live calendar " + self.live_calendar


class Vacation(models.Model):
    """Representation of a vacation block of time for employee absentee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_datetime = models.DateTimeField('start datetime', db_index=True, default=timezone.now)
    end_datetime = models.DateTimeField('end datetime', db_index=True, default=timezone.now)

    employee = models.ForeignKey(Employee, db_index=True)


    def __str__(self):
        start_str = self.end_datetime.strftime("%Y/%m/%d")
        end_str = self.end_datetime.strftime("%Y/%m/%d")

        return ("Vacation for employee: " + self.employee.first_name  + " " + 
                self.employee.last_name + " from " + start_str + " - " + end_str)
        
        
class VacationApplication(models.Model):
    """Representation of a vacation application created by an employee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_datetime = models.DateTimeField('start datetime', db_index=True, default=timezone.now)
    end_datetime = models.DateTimeField('end datetime', db_index=True, default=timezone.now)
    employee = models.ForeignKey(Employee, db_index=True)
    
    note = models.CharField('Note', default="", blank=True, max_length=280)
    approved = models.NullBooleanField(default=None, blank=True)
    datetime_of_approval =  models.DateTimeField('Datetime of approval', db_index=True, blank=True, null=True, default=timezone.now)
    

    def __str__(self):
        start_str = self.end_datetime.strftime("%Y/%m/%d")
        end_str = self.end_datetime.strftime("%Y/%m/%d")

        return ("Vacation application for employee: " + self.employee.first_name 
                + " " + self.employee.last_name + " from " + start_str + " - " + end_str)
        

class Absence(models.Model):
    """Representation of an absent block of time for employee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_datetime = models.DateTimeField('start datetime', db_index=True, default=timezone.now)
    end_datetime = models.DateTimeField('end datetime', db_index=True, default=timezone.now)

    employee = models.ForeignKey(Employee, db_index=True)


    def __str__(self):
        start_str = self.end_datetime.strftime("%Y/%m/%d")
        end_str = self.end_datetime.strftime("%Y/%m/%d")

        return "Unavailability for employee: " + self.employee.last_name + " from " + start_str + " - " + end_str
        
        
class AbsenceApplication(models.Model):
    """Representation of an absent application created by an employee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_datetime = models.DateTimeField('start datetime', db_index=True, default=timezone.now)
    end_datetime = models.DateTimeField('end datetime', db_index=True, default=timezone.now)
    employee = models.ForeignKey(Employee, db_index=True)

    note = models.CharField('Note', default="", blank=True, max_length=280)
    approved = models.NullBooleanField(default=None, blank=True)
    datetime_of_approval =  models.DateTimeField('Datetime of approval', db_index=True, blank=True, null=True, default=timezone.now)
    
    
    def __str__(self):
        start_str = self.end_datetime.strftime("%Y/%m/%d")
        end_str = self.end_datetime.strftime("%Y/%m/%d")

        return "Unavailability for employee: " + self.employee.name + " from " + start_str + " - " + end_str


class RepeatUnavailability(models.Model):
    """Representation of repeating unavailability for employee absentee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_time = models.DateTimeField('start time', db_index=True, default=timezone.now)
    end_time = models.DateTimeField('end time', db_index=True, default=timezone.now)
    # Weekday starts on Monday, so Monday = 0, Tuesday = 1, etc.
    weekday = models.IntegerField('weekday')

    employee = models.ForeignKey(Employee, db_index=True)


    def __str__(self):
        return "Employee %s on weekday: %s, from %s until %s" % (self.employee.last_name,
                                                                 self.weekday,
                                                                 self.start_time.time(),
                                                                 self.end_time.time())
                                                                 
                                                                 
class RepeatUnavailabilityApplication(models.Model):
    """Representation of repeating unavailability application created by employee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_time = models.DateTimeField('start time', db_index=True, default=timezone.now)
    end_time = models.DateTimeField('end time', db_index=True, default=timezone.now)
    # Weekday starts on Monday, so Monday = 0, Tuesday = 1, etc.
    weekday = models.IntegerField('weekday')
    employee = models.ForeignKey(Employee, db_index=True)
    
    note = models.CharField('Note', default="", blank=True, max_length=280)
    approved = models.NullBooleanField(default=None, blank=True)
    datetime_of_approval =  models.DateTimeField('Datetime of approval', db_index=True, blank=True, null=True, default=timezone.now)


    def __str__(self):
        return "Employee %s on weekday: %s, from %s until %s" % (self.employee.last_name,
                                                                 self.weekday,
                                                                 self.start_time.time(),
                                                                 self.end_time.time())
                                                                 

class DesiredTime(models.Model):
    """Representation of repeating desired work time for employee."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    start_time = models.DateTimeField('start time', db_index=True, default=timezone.now)
    end_time = models.DateTimeField('end time', db_index=True, default=timezone.now)
    # Weekday starts on Monday, so Monday = 0, Tuesday = 1, etc.
    weekday = models.IntegerField('weekday', default=0)

    employee = models.ForeignKey(Employee, db_index=True)


    def __str__(self):
        return "Employee %s on weekday: %s, from %s until %s" % (self.employee.last_name,
                                                                 self.weekday,
                                                                 self.start_time.time(),
                                                                 self.end_time.time())
                                                                 

class MonthlyRevenue(models.Model):
    """Representation of total revenue for a business for given month & year."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    monthly_total = models.IntegerField('monthly total revenue', default=0)
    month_year = models.DateField('month and year', db_index=True, default=date.today)


    def __str__(self):
        date_str = self.month_year.strftime("%Y, %B")
        return "Monthly revenue for: " + date_str + ". Amount: " + self.monthly_total


class DayNoteHeader(models.Model):
    """Note for a given date that is rendered in a day's header near day number."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, db_index=True, default=1)

    date = models.DateField('Date', db_index=True, default=date.today)
    header_text = models.CharField('Note', default="", blank=True, max_length=140)


    def __str__(self):
        date_str = self.date.strftime("%Y/%m/%d")
        return "Day header note for department " + self.department.name + " on " + date_str


class DayNoteBody(models.Model):
    """Note for a given date that is rendered in a day's body near schedules."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, db_index=True, default=1)

    date = models.DateField('Date', db_index=True, default=date.today)
    body_text = models.CharField('Note', default="", blank=True, max_length=280)


    def __str__(self):
        date_str = self.date.strftime("%Y/%m/%d")
        return "Day body note for department " + self.department.name + " on " + date_str


class ScheduleSwapPetition(models.Model):
    """Object to store information about schedule swap petition."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    live_schedule = models.ForeignKey(LiveSchedule, db_index=True,
                                      null=True)
    employee = models.ForeignKey(Employee, db_index=True)
    note = models.CharField('Note', default="", blank=True, max_length=280)
    approved = models.NullBooleanField(default=None, blank=True)


    def __str__(self):
        return "Schedule swap petition for " + self.employee + ". Is approved? " + self.approved


class ScheduleSwapApplication(models.Model):
    """Object to store information about a schedule swap application."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    schedule_swap_petition = models.ForeignKey(ScheduleSwapPetition, db_index=True)
    employee = models.ForeignKey(Employee, db_index=True)
    approved = models.NullBooleanField(default=None, blank=True)


    def __str__(self):
        return "Schedule swap petition for " + self.employee + ". Is approved? " + self.approved


class BusinessData(models.Model):
    """Collection of misc. business data, like overtime."""
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

    # Company Name
    company_name = models.CharField(default="", max_length=120)

    # Business Settings
    overtime = models.IntegerField('Overtime In Hours', default=40)
    overtime_multiplier = models.FloatField('Overtime Multiplier', default=1.5)
    workweek_weekday_start = models.IntegerField('weekday', default=6)
    workweek_time_start = models.TimeField('start time', default=time(0, 0, 0))

    # Calendar Display Settings
    display_am_pm = models.BooleanField(default=False)
    display_minutes = models.BooleanField(default=True)
    display_nonzero_minutes = models.BooleanField(default=False)
    display_last_names = models.BooleanField(default=False)
    display_first_char_last_name = models.BooleanField(default=False)
    display_first_char_last_name_non_unique_first_name = models.BooleanField(default=False)
    time_picker_interval = models.IntegerField('time interval', default=30)
    desired_hours_overshoot_alert = models.IntegerField('Desired Hours Overshoot Alert', default=5)
    sort_by_names = models.BooleanField(default=False)
    unique_row_per_employee = models.BooleanField(default=True)

    #Last schedule times/options selected
    schedule_start = models.TimeField('start time', default=time(8, 0, 0))
    schedule_end = models.TimeField('start time', default=time(17, 0, 0))
    hide_start = models.BooleanField(default=False)
    hide_end = models.BooleanField(default=False)

    # Last calendar loaded of manager user
    last_cal_date_loaded = models.DateField('last_cal_date', default=date.today, null=True)
    last_cal_department_loaded = models.ForeignKey(Department, default=None, on_delete=models.SET_NULL, null=True)

    # Availability creation by employee rights
    right_to_submit_availability = models.BooleanField(default=False)

    def __str__(self):
        date_str = self.date.strftime("%Y/%m/%d")
        return "Business profile for company " + self.company_name
