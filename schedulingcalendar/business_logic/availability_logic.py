import json
import bisect
import calendar
from datetime import date, datetime, timedelta, time
from operator import itemgetter
from django.utils import timezone
from django.contrib.auth.models import User
from .time_logic import (check_for_overtime, calculate_weekly_hours_with_sch, 
                         calculate_weekly_hours, time_dur_in_hours, 
                         get_start_end_of_calendar)
from ..models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime, LiveSchedule, LiveCalendar,
                     LiveCalendarDepartmentViewRights, LiveCalendarEmployeeViewRights,
                     LiveCalendarVersionTimestamp)

                     

def get_eligibles(user, schedule):
    """Return a sorted list of eligible employees along with info.
    
    The eligible list is a sorted list of dictionaries containing an employee, 
    a sub-dictionary containing any potential conflicts the eligible employee 
    has relative to the schedule, and a tuple of integers that represents 
    multiple criterion for sorting their 'eligability'.
    
    Eligability is determined by how few conflicts the employee has with the
    schedule. An employee that has no conflicting schedules, has no conflicting 
    time off, is not in overtime, etc. is a more 'eligible' employee for the 
    schedule than, say, an employee who asks for time off that overlaps with 
    the schedule and is already working overtime. These conflicts are kept
    track of via the availability dictionary.
    
    The eligability is sorted according to tiers. That is, the eligible list
    is sorted multiple times. Each tier has a helper function that gives the
    desired integer value that 'scores' the employee's eligability. The list is
    sorted first according to the first tier, then each 'sub-list' demarcated 
    by the first tier is sorted by the second tier, and so on. This ensures
    that the overall sorting of the parent tier remains stable as each tier is 
    more individually refined/sorted.
    
    Tier 1 Sort: Availability conflicts (See get_availability)
    Tier 2 Sort: Priority of department for employee.
    Tier 3 Sort: Differential between overlap of employee's desired work hours 
                 and hours of the schedule.
    Tier 4 Sort: Differential between current amount of hours the employee is
                 assigned and how many hours a week the employee desires.
                 
    Args:
        user: django authenticated manager user.
        schedule: schedule to calculate employee eligability for assignment. 
    Returns:
        A dict containing the schedule pk and eligible list. The eligible list 
        is a sorted list of eligible employees, along with their availability 
        dictionary (see get_availability) and their sorting score.
    """
    
    eligables = []
    
    dep_membership = DepartmentMembership.objects.filter(user=user, department=schedule.department)
    for dep_mem in dep_membership:
        employee = dep_mem.employee
        availability = get_availability(user, employee, schedule)
        # Get the multiple-criterion tuple for sorting an employee
        availability_score = _calculate_availability_score(availability)
        dep_priority_score = _calculate_dep_priority_score(dep_mem)
        desired_times_score = _calculate_desired_times_score(availability['Desired Times'], 
                                                             schedule)
        desired_hours_score = _calculate_desired_hours_score(availability['Hours Scheduled'],
                                                             employee)
        sorting_score = (availability_score, dep_priority_score, 
                         desired_times_score, desired_hours_score)
                         
        eligables.append({'employee': employee, 
                          'availability': availability, 
                          'sorting_score': sorting_score})
        
    eligables.sort(key=lambda e: e['sorting_score'])
    return {'schedule': schedule, 'eligables': eligables}
    
    
def _calculate_availability_score(availability):
    """Calculate availability of employee given conflicts.
        
    S = 16, V = 8, A = 4, U = 2, O = 1
        
    The score for each availability tier is greater than the sum of all
    lesser conflicts combined. This ensures that a combination of lesser
    conflicts does not override a larger, more serious conflict.
    
    Mathematically this means that the next level of conflict's score will be
    the sum of all the lesser conflicts + 1, or 2^n, where n is the integer
    number representing that tier of conflict.
    
    Args:
      availability: The availability dict containing conflict information.
    Returns:
      score: An integer value of conflict. Higher score means more conflicts.
    """
    
    score = 0
    
    if availability['(S)']: score += 16
    if availability['(V)']: score += 8
    if availability['(A)']: score += 4
    if availability['(U)']: score += 2
    if availability['(O)']: score += 1
    
    return score
    
    
def _calculate_dep_priority_score(dep_member):
    """Calculate if the schedule's department is the employee's main dep.
    
    Sort list by priority of department for employee, 0 means main department.
    A larger number means the employee can sometimes be a part of this
    department, but it is not their usual department, thus a higher score
    puts them lower on the list of eligablity.
    
    Args:
        dep_member: Django DepartmentMembership model.
    Returns:
        Integer score of employee's relationship to department of schedule.
    """
    
    return dep_member.priority
    
    
def _calculate_desired_times_score(desired_times, schedule):
    """Calculate if schedule has overlap with employee's desired working times.
    
    Employees are able to set days and hours that they would prefer to work.
    If a schedule overlaps with these desired times, the employee is more
    eligible for the schedule than those who don't have overlapping desired
    time.
    
    The desired time's score is the negative value of the total number of
    seconds that the schedule overlaps with desired times the employee wishes
    to work. In order to do this we must convert datetime.time objects to 
    datetime.datetime objects in order to do arithmetic on time objects. This
    is then converted back into a timedelta object and converted into seconds.
    
    Args:
        desired_times: Queryset containing any desired times that overlaps
            with the schedule's weekday and times.
        schedule: Schedule model object. 
    Returns:
        Float number representing time in seconds of overlap of desired time
        employee wishes to work during and the schedule's time. The number is 
        made negative due to python's built in sorting method sorting from
        smallest to largest.
    """                       
    s_start = schedule.start_datetime
    s_end = schedule.end_datetime
    
    total_overlapping_time = timedelta(0)
    
    for desired_t in desired_times:
        # Create desired time dates as schedule date, to compare times
        d_start = s_start.replace(hour=desired_t.start_time.hour, 
                                  minute=desired_t.start_time.minute)
        d_end = s_end.replace(hour=desired_t.end_time.hour, 
                              minute=desired_t.end_time.minute)
        
        # Add up overlap of time between desired time and schedule
        if d_end < s_end and d_start < s_start:
            total_overlapping_time += d_end - s_start
            
        elif d_end > s_end and d_start < s_start:
            total_overlapping_time += s_end - s_start
            
        elif d_end < s_end and d_start > s_start:
            total_overlapping_time += d_end - d_start
            
        else:
            total_overlapping_time += s_end - d_start
        
    return -1 * total_overlapping_time.seconds
    
    
def _calculate_desired_hours_score(hours_scheduled, employee):
    """Calculate difference between curr # of hours worked and desired # hours.

    The smaller the difference between current number of hours assigned to 
    employee (Including the schedule they may be assigned to.) the more
    eligible the employee is to be assigned to the schedule. Thus, an employee
    who wishes to work 30 hours, who if assigned to schedule will then work 30
    hours will have a score of 0. If the number of hours they'll be working is
    32 or 28, they'll have an equivalent score of 2. 
    
    The further an employee is from their desired hours per week the higher
    their score will be and thus via the sorting algorithm they will appear 
    lower on the list.
    
    Args:
        hours_scheduled: float number representing current hours employee is
            working that workweek if assigned to the schedule.
        employee: Django Employee model.
    Returns:
        Integer score of absolute difference between current scheduled hours 
        and employee's desired amount of hours per week.
    """
    
    return hours_scheduled - employee.desired_hours
    
    
def get_availability(user, employee, schedule):
    """Create the availability dictionary for employee given a schedule.
    
    Availability is a dictionary containing information about conflicts an
    employee will have with the given schedule. For example, if the schedule
    is for Tuesday from 10 am to 4 pm, but said employee is already assigned to
    a schedule on that same Tuesday from 12 pm to 6 pm, this function will
    add this to the availability dictionary as a schedule conflict. These 
    conflicts are used to weigh an employee's eligability. The more conflicts
    an employee has, the less eligible they are to be assigned to the schedule.
    
    Note for repeating unavailabilities and desired times: 
    
    Because repeating times don't have a proper full datetime (Their datetimes
    are merely used to record timezones in Django) we use the date of the the 
    schedule itself, in addition to the repeating/desired time's time, to create
    a full datetime coordinate that can be compared for any overlap. Without 
    this, a schedule from 8 pm to 2 am with only a time coordinate in certain 
    timezones would appear to end before they start, which would lead to errors
    where an unavailability is not seen by the program but does actually exist.
    
    The keys and the values held by the dictionary are:
      '(S)': A collection of schedule model objects that have any time overlap
             with the schedule employee may be assigned to.
      '(V)': A collection of vacation model objects that have any time overlap
             with the schedule employee may be assigned to.
      '(A)': A collection of absence model objects that have any time overlap
             with the schedule employee may be assigned to.
      '(U)': A collection of repeating unavailability model objects that have 
             any time overlap with the schedule employee may be assigned to. 
      'Desired Times': A collection of desired time model objects that have 
             any time overlap with the schedule employee may be assigned to. 
      'Hours Scheduled': A numerical representation of how many hour the 
             employee will be working for that work week if assigned to the
             schedule.
      '(O)': A boolean value representing if the hours scheduled value is 
             greater than the employer's legal overtime limit.
        
    Args:
        user: django authenticated manager user.
        employee: Employee model object.
        schedule: Schedule model object.
    Returns:
        availability: A dictionary containing keys that map to potential 
        conflicts the employee may have with the given schedule. Also,
        additional information such as how many hours the employee will
        be working in the work week if assigned to the schedule.
    """
    
    availability = {}
    
    # Get schedules employee is assigned to that overlap with schedule
    schedules = (Schedule.objects.filter(user=user, employee=employee.id,
                                         start_datetime__lt=schedule.end_datetime,
                                         end_datetime__gt=schedule.start_datetime)
                                 .exclude(pk=schedule.pk))
    availability['(S)'] = schedules
    
    # Get vacations employee is assigned to that overlap with schedule
    vacations = (Vacation.objects.filter(user=user, employee=employee.id,
                                         start_datetime__lt=schedule.end_datetime,
                                         end_datetime__gt=schedule.start_datetime)) 
                            
    availability['(V)'] = vacations
    
    # Get absences employee is assigned to that overlap with schedule
    absences = (Absence.objects.filter(user=user, employee=employee.id,
                                       start_datetime__lt=schedule.end_datetime,
                                       end_datetime__gt=schedule.start_datetime)) 
    availability['(A)'] = absences
           
    # Get repeat unavailabilities employee is assigned overlapping with schedule
    sch_weekday = schedule.start_datetime.weekday()
    start_time = schedule.start_datetime.time()
    end_time = schedule.end_datetime.time()
    unav_repeat_naive = RepeatUnavailability.objects.filter(user=user, 
                                                            employee=employee.id,
                                                            weekday=sch_weekday)
    unav_repeat_aware = []
    for un_av in unav_repeat_naive:
        start_dt = schedule.start_datetime.replace(hour=un_av.start_time.hour, 
                                                   minute=un_av.start_time.minute)
        end_dt = schedule.end_datetime.replace(hour=un_av.end_time.hour, 
                                               minute=un_av.end_time.minute)                                 
        if start_dt < schedule.end_datetime and end_dt > schedule.start_datetime:
            unav_repeat_aware.append(un_av)         
    availability['(U)'] = unav_repeat_aware

    # Get desired times employee is assigned overlapping with schedule
    desired_times_naive = DesiredTime.objects.filter(user=user, 
                                                     employee=employee.id,
                                                     weekday=sch_weekday)
    desired_times_aware = []
    for desired_time in desired_times_naive:
        start_dt = schedule.start_datetime.replace(hour=desired_time.start_time.hour, 
                                                   minute=desired_time.start_time.minute)
        end_dt = schedule.end_datetime.replace(hour=desired_time.end_time.hour, 
                                               minute=desired_time.end_time.minute)                                 
        if start_dt < schedule.end_datetime and end_dt > schedule.start_datetime:
            desired_times_aware.append(desired_time)
    availability['Desired Times'] = desired_times_aware

    # Check current hours worked for later evaluation of overtime       
    curr_hours, total_workweek_hours = calculate_weekly_hours_with_sch(user, employee, schedule)
    availability['Hours Scheduled'] = total_workweek_hours
    availability['curr_hours'] = curr_hours
    availability['(O)'] = check_for_overtime(total_workweek_hours, user)
            
    return availability
    
    
def get_tro_dates(user, department, lower_bound_dt, upper_bound_dt):
    """Create a dict mapping dates to employees of department with time 
    requested off for that date.
    """
    dep_memberships = (DepartmentMembership.objects.filter(user=user, department=department))
    employee_pks = []
    for dep_mem in dep_memberships:
        employee_pks.append(dep_mem.employee.id)
        
    dep_vacations = Vacation.objects.filter(user=user,
                                            start_datetime__lt=upper_bound_dt,
                                            end_datetime__gt=lower_bound_dt,
                                            employee__in=employee_pks)
                                            
    unavailabilities = Absence.objects.filter(user=user,
                                              start_datetime__lt=upper_bound_dt,
                                              end_datetime__gt=lower_bound_dt,
                                              employee__in=employee_pks)
                                            
    return {'vacations': dep_vacations, 'unavailabilities': unavailabilities}

    
def create_live_schedules(user, live_calendar):
    """Create live schedules for given date and department."""
    # Get date month for calendar for queries
    cal_date = datetime.combine(live_calendar.date, time.min)
    lower_bound_dt, upper_bound_dt = get_start_end_of_calendar(cal_date.year, cal_date.month)
    
    # Get schedule and employee models from database appropriate for calendar
    schedules = (Schedule.objects.select_related('employee', 'department')
                                 .filter(user=user,
                                         start_datetime__gte=lower_bound_dt,
                                         end_datetime__lte=upper_bound_dt,
                                         department=live_calendar.department,
                                         employee__isnull=False))
    # Create mirror live schedules of schedule objects
    live_schedules = []
    for schedule in schedules:
        live_schedule = LiveSchedule(user=schedule.user,
                                     schedule=schedule,
                                     calendar=live_calendar,
                                     version=live_calendar.version,
                                     start_datetime=schedule.start_datetime, 
                                     end_datetime=schedule.end_datetime,
                                     hide_start_time=schedule.hide_start_time,
                                     hide_end_time=schedule.hide_end_time,
                                     schedule_note=schedule.schedule_note,
                                     department=schedule.department,
                                     employee=schedule.employee)
        live_schedules.append(live_schedule)
        
    LiveSchedule.objects.bulk_create(live_schedules)
    
    
def create_live_cal_timestamp(user, live_calendar):
    """Create timestamp corresponding to live calendar's published version."""
    live_cal_timestamp = LiveCalendarVersionTimestamp(user=user, calendar=live_calendar,
                                                      version=live_calendar.version,
                                                      timestamp=timezone.now())
    live_cal_timestamp.save()