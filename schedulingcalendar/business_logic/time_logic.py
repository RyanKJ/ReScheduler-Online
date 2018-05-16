import json
import bisect
import calendar
from datetime import date, datetime, timedelta, time
from operator import itemgetter
from django.utils import timezone
from django.contrib.auth.models import User
from ..models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime, LiveSchedule, LiveCalendar,
                     LiveCalendarDepartmentViewRights, LiveCalendarEmployeeViewRights)


def check_for_overtime(hours, user):
    """Calculate if number of hours is in overtime or not."""
    business_data = BusinessData.objects.get(user=user)
    
    if hours > business_data.overtime:
        return True
    else:
        return False
    
    
def calculate_weekly_hours_with_sch(user, employee, schedule):
    """Calculate # of hours employee will be working if assigned to schedule.
    
    Given the employer's stated start of the week, say Friday, sum up the total
    amount of time employee will be working for that week along with the length
    of time of the schedule itself. So, if the schedule is 8 hours long and 
    the employee is working 40 hours already, then the returned value is 48.
    
    Args:
        user: django authenticated manager user.
        employee: Employee model object.
        schedule: Schedule model object.
    Returns:
        A tuple value of how many hours that employee is working currently
        as the first value and how many hours the employee will be working if
        assigned to schedule as the second value.
    """
    
    curr_hours = calculate_weekly_hours(employee, schedule.start_datetime, user)
    if schedule.employee == employee:
        return (curr_hours, curr_hours)
    else:
        min_time_for_break = employee.min_time_for_break
        break_time_min = employee.break_time_in_min
        time_with_sch =  curr_hours + time_dur_in_hours(schedule.start_datetime, schedule.end_datetime,
                                                        None, None, min_time_for_break, break_time_min)
        return (curr_hours, time_with_sch)
    
    
def calculate_weekly_hours(employee, dt, user):
    """Calculate # of hours employee works for workweek containing datetime.
            
    Args: 
        employee: django employee object.
        dt: datetime that is contained within the start, end datetimes of workweek.
        user: authenticated user who called function.
    Returns:
        float number representing hours employee works for a given workweek.
    """
    
    # TODO: Take getting workweek out of method: unnecessary queries
    workweek_datetimes = get_start_end_of_weekday(dt, user)
    min_time_for_break = employee.min_time_for_break
    break_time_min = employee.break_time_in_min
    schedules = (Schedule.objects.filter(user=user,
                                         employee=employee,
                                         start_datetime__gte=workweek_datetimes['start'],
                                         start_datetime__lte=workweek_datetimes['end'])
                                 .order_by('start_datetime', 'end_datetime'))
                                                                     
    hours = 0
    for schedule in schedules:
        hours += time_dur_in_hours(schedule.start_datetime, schedule.end_datetime,
                                   None, None, min_time_for_break, break_time_min)

    return hours
    
    
def get_start_end_of_weekday(dt, user):
    """Return start and end datetimes of workweek that contain datetime inside
    
    Because users are allowed to pick a specific day and time for the start
    of the workweek, one cannot assume the workweek will start on a monday at
    12:00 am. In order to calculate the start datetime of a workweek, we first
    find the start date relative to some date that must be contained within 
    the workweek
    """
    
    business_data = BusinessData.objects.get(user=user)
    start_day_of_week = business_data.workweek_weekday_start
    start_time_of_week = business_data.workweek_time_start
    dt_weekday = dt.weekday()
    
    if start_day_of_week < dt_weekday:
        day_difference = dt_weekday - start_day_of_week
    elif start_day_of_week > dt_weekday:
        day_difference = dt_weekday + (7 - start_day_of_week)
    # Case where start of workweek weekday is equal to datetime weekday
    else:
        # Case where start time of workweek is before datetime's time
        if start_time_of_week < dt.time():
            day_difference = 0
        # Case where datetime comes before start of work week start time
        # So we subtract 7 days since it belongs to 'last week'
        else:
            day_difference = 7
        
    start_date_of_week = dt.date() - timedelta(day_difference)
    start_dt = datetime.combine(start_date_of_week, start_time_of_week)
    start_datetime_of_week = timezone.make_aware(start_dt)
    end_datetime_of_week = start_datetime_of_week + timedelta(7) - timedelta(seconds=1)
    
    return {'start': start_datetime_of_week, 'end': end_datetime_of_week}
    
    
def time_dur_in_hours(start_datetime, end_datetime, 
                      start_lowerb=None, end_upperb=None, 
                      min_time_for_break=None,
                      break_time_in_min=None):
    """Calculate length of time in hours, represented as a float number
    
    Args:
        start_datetime: python datetime marking beginning of time duration
        end_datetime: python end datetime marking end of time duration
        start_lowerb: Python datetime as furthest back in time to calculate
            duration. If both lower and upper bound are present then truncate
            the start and end datetimes if they lie outside the bounds.
        end_lowerb: Python datetime as furthest far in time to calculate 
            duration.
        break_time: Float number representing number of minutes of break time
            to subtract from the overall duration.
    Returns:
        A float representing number of hours of time duration.
    """
    
    if not start_lowerb or not end_upperb:
        start = start_datetime
        end = end_datetime
    else: # Potentially truncate times according to the time bounds
        if start_datetime >= start_lowerb:
            start = start_datetime
        else:
            start = start_lowerb
        if end_datetime <= end_upperb:
            end = end_datetime
        else:
            end = end_upperb
    
    time_delta = end - start
    hours = time_delta.seconds / 3600.0
    
    if min_time_for_break and min_time_for_break <= hours:
        hours -= break_time_in_min / 60.0
    
    return hours
    
    
def get_dates_in_week(date):
    """Given date, return all dates that fall in week of date.
    
    Args:
        Python date object
    Returns:
        A list of python dates objects that represent each date in a week,
        where Sunday is the first day of the week.
    """
    
    week_dates = []
    week_day = date.weekday()

    start_of_week = date
    if week_day != 6: # 6 means Sunday, 0 means Monday
        start_of_week = date - timedelta(week_day + 1)
        
    for i in range(0, 7):
        week_date = start_of_week + timedelta(i)
        week_dates.append(week_date)
    
    return week_dates
    
    
def get_start_end_of_calendar(year, month):
    """Return start and end datetimes of a calendar, given first date of month.
    
    For any given calendar, the start and end dates of the month are not
    necessarily the start and end dates of the calendar, because the calendar
    includes days of months before and after the calendar's 'month' because 
    a calendar displays the whole week the start and end of the month are
    a part of. 
    
    For example, if the start of February is a Tuesday, then the calendar will
    display Sunday and Monday of the last week of January as well.

    Args:
        year: Integer value of year.
        month: Integer value of month.
    Returns:
        A tuple of the start and end datetimes of the calendar.
    """
    
    cal_date = datetime(year, month, 1)
    last_day_num_of_month = calendar.monthrange(year, month)[1]
    last_date_of_month = datetime(year, month, last_day_num_of_month)
    start_of_month_weekday = cal_date.isoweekday()
    end_of_month_weekday = last_date_of_month.isoweekday()
    lower_bound_dt = cal_date - timedelta(start_of_month_weekday % 7)
    upper_bound_dt = (last_date_of_month 
                      + timedelta(((6 - end_of_month_weekday) % 7) + 1) 
                      - timedelta(seconds=1))
    
    return (lower_bound_dt, upper_bound_dt)