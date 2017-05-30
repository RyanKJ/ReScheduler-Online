"""
Author: Ryan Johnson

Python module containing business logic. Functions for processing eligability
of employees and getting employee availability for a given schedule are
contained here.
"""

import json
import bisect
from datetime import date, datetime, timedelta
from operator import itemgetter
from django.utils import timezone
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from .models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime)


def get_eligables(schedule):
    """Return a sorted list of eligable employee's along with info.
    
    The eligable list is a sorted list of employees, a dictionary containing 
    any potential conflicts the eligable employee has relative to the schedule,
    and a tuple of integers that represents multiple criterion for sorting 
    their 'eligability'.
    
    Eligability is determined by how few conflicts the employee has with the
    schedule. An employee that has no conflicting schedules, has no conflicting 
    time off, is not in overtime, etc. is a more 'eligable' employee for the 
    schedule than, say, an employee who asks for time off that overlaps with 
    the schedule and is already working overtime. These conflicts are kept
    track of via the availability dictionary.
    
    The eligability is sorted according to tiers. That is, the eligable list
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
        schedule: schedule to calculate employee eligability for assignment. 
    Returns:
        A dict containing the schedule pk and eligable list. The eligable list 
        is a sorted list of eligable employees, along with their availability 
        dictionary (see get_availability) and their sorting score.
    """
    
    eligables = []
    
    dep_membership = DepartmentMembership.objects.filter(department=schedule.department)
    for dep_mem in dep_membership:
        employee = dep_mem.employee
        availability = get_availability(employee, schedule)
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
    eligable for the schedule than those who don't have overlapping desired
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
    
    sch_weekday = schedule.start_datetime.weekday()
    start_time = schedule.start_datetime.time()
    end_time = schedule.end_datetime.time()
    today = date.today()
                                                
    total_overlapping_time = timedelta(0)
    
    for d_t in desired_times:
        if d_t.end_time < end_time and d_t.start_time < start_time:
            start = datetime.combine(today, start_time)
            end = datetime.combine(today, d_t.end_time)
            total_overlapping_time += end - start
        elif d_t.end_time > end_time and d_t.start_time < start_time:
            start = datetime.combine(today, start_time)
            end = datetime.combine(today, end_time)
            total_overlapping_time += end - start
        elif d_t.end_time < end_time and d_t.start_time > start_time:
            start = datetime.combine(today, d_t.start_time)
            end = datetime.combine(today, d_t.end_time)
            total_overlapping_time += end - start
        else:
            start = datetime.combine(today, d_t.start_time)
            end = datetime.combine(today, end_time)
            total_overlapping_time += end - start
        
    return -1 * total_overlapping_time.seconds
    
    
def _calculate_desired_hours_score(hours_scheduled, employee):
    """Calculate difference between curr # of hours worked and desired # hours.

    The smaller the difference between current number of hours assigned to 
    employee (Including the schedule they may be assigned to.) the more
    eligable the employee is to be assigned to the schedule. Thus, an employee
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
    
    
def get_availability(employee, schedule):
    """Create the availability dictionary for employee given a schedule.
    
    Availability is a dictionary containing information about conflicts an
    employee will have with the given schedule. For example, if the schedule
    is for Tuesday from 10 am to 4 pm, but said employee is already assigned to
    a schedule on that same Tuesday from 12 pm to 6 pm, this function will
    add this to the availability dictionary as a schedule conflict. These 
    conflicts are used to weigh an employee's eligability. The more conflicts
    an employee has, the less eligable they are to be assigned to the schedule.
    
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
    schedules = (Schedule.objects.filter(employee=employee.id,
                                         start_datetime__lt=schedule.end_datetime,
                                         end_datetime__gt=schedule.start_datetime)
                                 .exclude(pk=schedule.pk))
    availability['(S)'] = schedules
    
    # Get vacations employee is assigned to that overlap with schedule
    vacations = (Vacation.objects.filter(employee=employee.id,
                                         start_datetime__lt=schedule.end_datetime,
                                         end_datetime__gt=schedule.start_datetime)) 
    availability['(V)'] = vacations
    
    # Get absences employee is assigned to that overlap with schedule
    absences = (Absence.objects.filter(employee=employee.id,
                                       start_datetime__lt=schedule.end_datetime,
                                       end_datetime__gt=schedule.start_datetime)) 
    availability['(A)'] = absences
           
    # Get repeat unavailabilities employee is assigned overlapping with schedule
    sch_weekday = schedule.start_datetime.weekday()
    start_time = schedule.start_datetime.time()
    end_time = schedule.end_datetime.time()
    unav_repeat = (RepeatUnavailability.objects.filter(employee=employee.id,
                                                       weekday=sch_weekday,
                                                       start_time__lt=end_time,
                                                       end_time__gt=start_time))
    availability['(U)'] = unav_repeat     

    # Get desired times employee is assigned overlapping with schedule
    desired_times = (DesiredTime.objects.filter(employee=employee.id,
                                                weekday=sch_weekday,
                                                start_time__lt=end_time,
                                                end_time__gt=start_time))
    availability['Desired Times'] = desired_times

    # Check current hours worked for later evaluation of overtime       
    total_workweek_hours = calculate_weekly_hours_with_sch(employee, schedule)
    availability['Hours Scheduled'] = total_workweek_hours
    availability['(O)'] = check_for_overtime(total_workweek_hours, schedule.user)
            
    return availability
    
    
def check_for_overtime(hours, user):
    """Calculate if number of hours is in overtime or not."""
    business_data = BusinessData.objects.get(user=user, pk=1)
    
    if hours > business_data.overtime:
        return True
    else:
        return False
    
    
def calculate_weekly_hours_with_sch(employee, schedule):
    """Calculate # of hours employee will be working if assigned to schedule.
    
    Given the employer's stated start of the week, say Friday, sum up the total
    amount of time employee will be working for that week along with the length
    of time of the schedule itself. So, if the schedule is 8 hours long and 
    the employee is working 40 hours already, then the returned value is 48.
    
    Args:
        employee: Employee model object.
        schedule: Schedule model object.
    Returns:
        An integer value of how many hours that employee will be working for
        that with, including the hours of the schedule they may be assigned to.
    """
    
    # TODO: Not count overlapping time of to be assigned schedule.
    
    curr_hours = calculate_weekly_hours(employee, schedule.start_datetime, schedule.user)
    return curr_hours + time_dur_in_hours(schedule.start_datetime, schedule.end_datetime)
    
    
def calculate_weekly_hours(employee, dt, user):
    """Calculate # of hours employee works for workweek containing datetime.
    
    This function does not count overlapping time. That is, if an employee is
    assigned a 9-5 schedule on the same date in two different departments, it 
    will be counted as one schedule. (This is because an employee can be both
    a floral designer making flower arrangements and a staff member helping
    customers, in a floral business example.) So, this function would count
    that employee as working for 8 hours instead of 16 hours.
    
    In order to not count overlapping time the summed schedules are queried
    in a sorted fashion and then their time duration is summed up. But since
    schedules can potentially overlap one cannot just sum up the duration of 
    each schedule independently. A variable, last_end_dt, is used to keep track
    of the end of the last schedule iterated over. This is used to check if the
    next schedule, which starts equally or later than the last schedule in the
    queryset due to the order_by method, has any overlap. There are three cases
    one can encounter:
    
    Case 1: Schedules don't overlap. Simply sum up time delta of schedule and
            set schedule's end_dt to be last_end_dt
    Case 2: Previous schedule's end_dt is greater than or equal to next schedule's 
            end_dt, skip adding time since it is contained entirely in a
            previous schedule.
    Case 3: Partial overlap, schedule starts before previous schedule ends, but
            ends after previous schedule ends. So count only the time that 
            does not overlap.
            
    Args: 
        employee: django employee object.
        dt: datetime that is contained within the start, end datetimes of workweek.
        user: authenticated user who called function.
    Returns:
        float number representing hours employee works for a given workweek, 
        not counting overlapping schedule times.
    """
    
    # TODO: Take getting workweek out of method: unnecessary queries
    workweek_datetimes = get_start_end_of_weekday(dt, user)
    schedules = (Schedule.objects.filter(user=user,
                                         employee=employee,
                                         start_datetime__gte=workweek_datetimes['start'],
                                         start_datetime__lt=workweek_datetimes['end'])
                                 .order_by('start_datetime', 'end_datetime'))
                                         
    #TODO: Not count time of schedules that overlap with 2 different workweeks
                                         
    hours = 0
    # Choose a date far in past to ensure the first end_dt > last_end_dt
    last_end_dt = timezone.now() - timedelta(31337)
    
    for schedule in schedules:
        if last_end_dt <= schedule.end_datetime: # Case 1
            hours += time_dur_in_hours(schedule.start_datetime, schedule.end_datetime)
            last_end_dt = schedule.end_datetime
        elif last_end_dt >= schedule.end_datetime: # Case 2
            continue
        else: # Case 3
            hours += time_dur_in_hours(last_end_dt, schedule.end_datetime)
            last_end_dt = schedule.end_datetime
    
    return hours
    
    
def eligable_list_to_dict(eligable_list):
    """Convert eligable_list into a dict ready for json serialization.
    
    Args:
        eligable_list: list of sorted eligables with an availability dict and
        a sorting score.
    Returns:
        The eligable list formatted into dicts to be serialized by json.
    """
    
    eligable_serialized_list = []
    
    for e in eligable_list['eligables']:
        eligable_serialized = {}
        eligable_serialized_list.append(eligable_serialized)
        
        # Serialize the employee model
        employee_serialized = model_to_dict(e['employee'])
        eligable_serialized['employee'] = employee_serialized
        # Serialize the availability dict
        avail_serialized = _availability_to_dict(e['availability'])
        eligable_serialized['availability'] = avail_serialized
        
    # Serialize the corresponding schedule
    serialized_schedule = model_to_dict(eligable_list['schedule'])
    
    data = {'schedule': serialized_schedule, 
            'eligable_list': eligable_serialized_list}
            
    return data
    
    
def _availability_to_dict(availability):
    """Convert availability into a dict ready for json serialization.
    
    Args:
        availability: list containing django querysets and other information
        compiled by the get_availability function.
    Returns:
        Availability formatted into dicts to be serialized by json.
    """
    
    MODEL_AVAILABILITIES = ('(S)', '(V)', '(A)', '(U)', 'Desired Times')
    avail_serialized = {}
    
    for key in MODEL_AVAILABILITIES:
        serialized_conflicts = []
        for conflict in availability[key]:
            serial_conf = model_to_dict(conflict)
            serialized_conflicts.append(serial_conf)
            
        avail_serialized[key] = serialized_conflicts
            
    avail_serialized['(O)'] = availability['(O)']
    avail_serialized['Hours Scheduled'] = availability['Hours Scheduled']
    
    return avail_serialized
      
    
def date_handler(obj):
    """Add converting instructions to JSON parser for datetime objects. 
    
    Written by Anthony Hatchkins: 
    http://stackoverflow.com/questions/23285558/datetime-date2014-4-25-is-not-json-serializable-in-django
    """
    
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError
        
        
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
    end_datetime_of_week = start_datetime_of_week + timedelta(7)
    
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
    
    #TODO: Include subtracting hours for lunch breaks
    
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
    hours = time_delta.seconds / 3600
    
    if min_time_for_break and min_time_for_break >= hours:
        hours -= break_time_in_min / 60
    
    return hours
    

def get_avg_monthly_revenue(user, month):
    """Calculate average revenue of a given month.
    
    Args:
        user: django authenticated user
        month: integer value of month
    Returns:
        A floating number that is the average of all the monthly revenue's 
        entered by a user, or -1 if the user has no monthly revenue data points
        for the given month.
    """
    monthly_revenues = MonthlyRevenue.objects.filter(user=user,
                                                     month_year__month=month)
    num_of_data_points = len(monthly_revenues)
    
    if num_of_data_points > 0:
        sum = 0 
        for month_rev in monthly_revenues:
            sum += month_rev.monthly_total
        
        return sum / num_of_data_points
    else:
        return -1
    
    
def non_wage_monthly_costs(user, month, year, department):
    """Calculate the cost of benefits for a given calendar."""
    return 0
    

def all_calendar_costs(user, month, year):
    """Calculate cost of given month of schedules, including benefits.
    
    Args:
        user: django authenticated user
        month: integer value of month
        year: integer value of year
    Returns:
        A dict containing departments and corresponding float values
        representing dollar cost.
    """  
    
    departments = Department.objects.filter(user=user)
    business_data = BusinessData.objects.get(user=user)
    
    department_costs = {}
    workweeks = []
    
    # Create dict for department costs
    for department in departments:
        department_costs[department.id] = {'name': department.name, 'cost': 0}
    department_costs['total'] = {'name': 'Total', 'cost': 0}                                       
    
    # Get all workweeks with any intersection with month
    beginning_of_month = timezone.make_aware(datetime(year, month, 1))
    first_workweek = get_start_end_of_weekday(beginning_of_month, user)
    workweeks.append(first_workweek)
    for i in range(1, 6):
        ith_day = first_workweek['start'] + timedelta((i * 7) + 1)
        ith_workweek = get_start_end_of_weekday(ith_day, user)
        # If start of workweek is contained in month, add workweek
        if ith_workweek['start'].month == month:
            workweeks.append(ith_workweek)
        
    # Sum up costs for each workweek and add to department costs
    for workweek in workweeks:
        hours = workweek_hours(user, workweek['start'], workweek['end'], 
                               departments, business_data, month, year)
        costs = calculate_workweek_costs(hours, departments, business_data, True)
        
        for dep_id in costs:
            department_costs[dep_id]['cost'] += costs[dep_id]

    return department_costs
    
 
def workweek_hours(user, start_dt, end_dt, departments, business_data, 
                   month=None, year=None):
    """Return a dict containing working hours of employees given workweek.
    
    A workweek is defined as the start and end datetimes of a workweek. Since
    an employer can determine the start day and time of a workweek, workweeks
    are arbitrary with respect to employer. This function returns a dict
    containing employee django models as keys and dict as its value. These 
    sub-dicts contain key/value pairs where the department pk is the key and 
    the value is yet another dict containing the regular and overtime number
    of hours for that deparment in general, then the regular
    
    The nest of dicts looks something like:
        workweek_hours {
            employee_object {
                department_pk {
                    hours: float value
                    overtime_hours: float value
                    hours_in_month: float value
                    ovr_t_in_month: float value
                }
                ... More department pks
            }
            ... More employee models 
        }
        
    This data-structure allows for us to easily compute the total cost of each
    department for a gien workweek and also to know the regular and overtime
    hous that strictly fall within a given month.
    
    Args:
        user: django authenticated user
        start_dt: Python datetime representing start of workweek
        end_dt: Python datetime representing end of workweek
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user
        month: integer value of month. If value present, this function
            calculates schedules that only have overlapping time in the month.
            (Since often workweeks at start/end of month have days that are
            outside that month.)
        year: integer value of year. Optional value similar to month.
    Returns:
        A dict of employees that map to a sub-dict of float values representing
        how many hours and overtime hours that employee works both in the work-
        week and if month and year are supplied, how many hours an employee
        works in a workweek that only intersect with the month.
    """

    schedules = (Schedule.objects.select_related('department', 'employee')
                                 .filter(user=user,
                                         end_datetime__gt=start_dt,
                                         start_datetime__lt=end_dt)
                                 .exclude(employee=None)
                                 .order_by('start_datetime', 'end_datetime'))
                                 
    workweek_hours = {}
                                               
    # Sort queried schedules by employee                                                
    for schedule in schedules:
        if schedule.employee not in workweek_hours:
            workweek_hours[schedule.employee] = []
        workweek_hours[schedule.employee].append(schedule)
    
    # For each employee, get total hours worked that week
    for employee in workweek_hours:
        hours = workweek_hours_detailed(start_dt, end_dt, departments,
                                        business_data, workweek_hours[employee],
                                        month, year)
        workweek_hours[employee] = hours
        
    return workweek_hours
    
    
def calculate_workweek_costs(workweek_hours, departments, business_data, month_only=False):
    """Calculate the costs of workweek_hours data-structure and return cost.
    
    Args:
        workweek_hours: Dict of employees and their hours in that workweek.
        departments: List of all departments for managing user.
        business_data: Django model of business data for managing user
        month_only: Boolean to determine if to count all of the workweek costs
            or only days in the workweek that overlap with the month.
    Returns:
        A dict of key values mapping department to float number costs in
        dollars.
    """
    
    # TODO: Add hourly associated benefits cost like social security, workmans comp
    ovr_t_multiplier = business_data.overtime_multiplier
    workweek_costs = {}
    
    for department in departments:
        workweek_costs[department.id] = 0
    workweek_costs['total'] = 0
    
    for employee in workweek_hours:
        dep_hours = workweek_hours[employee]
        
        for department in dep_hours:
            if month_only:
                regular_cost = dep_hours[department]['hours_in_month'] * employee.wage
                over_t_cost = dep_hours[department]['ovr_t_in_month'] * employee.wage * ovr_t_multiplier
            else:
                regular_cost = dep_hours[department]['hours'] * employee.wage
                over_t_cost = dep_hours[department]['overtime_hours'] * employee.wage * ovr_t_multiplier
            
            workweek_costs[department] += regular_cost + over_t_cost
        
    return workweek_costs    
    
        
def workweek_hours_detailed(start_dt, end_dt, departments, business_data, schedules, 
                            month=None, year=None):
    """Calculate the number of hours and overtime hours for given schedules.
    
    This function works similarly to calculate_weekly_hours in that it does
    not count time overlapping between multiple schedules for one employee as
    different times. So we ensure we do not count time where employee is 
    present at work for a day in 2 different departments twice. The first
    occuring schedule is the department whose hours are counted in the case of
    an overlap.
   
    Then we count the number of hours the employee is working both in that 
    department and overall all departments for that workweek. Furthermore, 
    since we are interested in the ratio of employment costs to average monthly 
    revenue, keep a running sum of the regular and overtime hours of schedules
    that strictly belong to a given month and year. This is because workweeks 
    at the start and end of a month contain schedules that fall outside that
    month. This running sum allows us to calculate costs of scheduling that 
    strictly belong to a given month, giving us an accurate ratio of employment 
    cost to average monthly revenue.
    
    Note that for monthly hours, schedules that start and end in 2 different
    months may or may not be counted. This inaccuracy is deliberate in order
    to keep the code both readable and response times for the user as fast as
    possible. This potential error is considered tolerable due to the purpose
    of scheduling cost / average revenue as a loose guideline for managers to
    create schedules.
    
    Args:
        start_dt: Python datetime representing start of workweek
        end_dt: Python datetime representing end of workweek
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user
        schedules: Sorted queryset of schedules to be calculated. Usually all 
            schedules for an employee that have any intersection with a 
            particular workweek.
        month: integer value of month. If value present, this function
            calculates schedules that only have overlapping time in the month.
            (Since often workweeks at start/end of month have days that are
            outside that month.)
        year: integer value of year. Optional value similar to month.
    Returns:
        A dict containing the values of how many hours and overtime hours
        the schedules will add up to given the start and end times of a
        workweek.
    """
                     
    # Create hours dict to keep track of hours for each department
    overtime = business_data.overtime
    min_time_for_break = business_data.min_time_for_break
    break_time_min = business_data.break_time_in_min
    employee_hours = {}
    
    for dep in departments:
        employee_hours[dep.id] = {'hours': 0, 'overtime_hours': 0, 
                                  'hours_in_month': 0, 'ovr_t_in_month': 0}
    employee_hours['total'] = {'hours': 0, 'overtime_hours': 0, 
                               'hours_in_month': 0, 'ovr_t_in_month': 0}
    
    # Choose a date far in past to ensure the first end_dt > last_end_dt
    last_end_dt = timezone.now() - timedelta(31337)
    
    for schedule in schedules:
        if last_end_dt <= schedule.end_datetime: # Case 1
            schedule_hours = time_dur_in_hours(schedule.start_datetime, 
                                               schedule.end_datetime,
                                               start_dt, end_dt, 
                                               min_time_for_break, 
                                               break_time_min)
            last_end_dt = schedule.end_datetime
        elif last_end_dt >= schedule.end_datetime: # Case 2
            continue
        else: # Case 3
            schedule_hours = time_dur_in_hours(last_end_dt, 
                                               schedule.end_datetime,
                                               start_dt, end_dt,
                                               min_time_for_break, 
                                               break_time_min)
            last_end_dt = schedule.end_datetime
            
        # Calculate hours in the workweek
        overall_hours = employee_hours['total']['hours'] + schedule_hours
        if overall_hours > overtime:
            overtime_hours = overall_hours - overtime
            regular_hours = schedule_hours - overtime_hours
            
            # Add all regular and overtime hours in workweek
            employee_hours['total']['hours'] += regular_hours
            employee_hours[schedule.department.id]['hours'] += regular_hours
            employee_hours['total']['overtime_hours'] += overtime_hours
            employee_hours[schedule.department.id]['overtime_hours'] += overtime_hours
            
            # Add all hours in workweek only if schedule is strictly in month
            sch_month = schedule.start_datetime.month
            sch_year = schedule.start_datetime.year
            if sch_month == month and sch_year == year:
                employee_hours['total']['hours_in_month'] += regular_hours
                employee_hours[schedule.department.id]['hours_in_month'] += regular_hours
                employee_hours['total']['ovr_t_in_month'] += overtime_hours
                employee_hours[schedule.department.id]['ovr_t_in_month'] += overtime_hours
        else:
            # Add all regular and overtime hours in workweek
            employee_hours['total']['hours'] += schedule_hours
            employee_hours[schedule.department.id]['hours'] += schedule_hours
                
            # Add all hours in workweek only if schedule is strictly in month
            sch_month = schedule.start_datetime.month
            sch_year = schedule.start_datetime.year
            if sch_month == month and sch_year == year:
                employee_hours['total']['hours_in_month'] += schedule_hours
                employee_hours[schedule.department.id]['hours_in_month'] += schedule_hours
    
    return employee_hours       
    
    
def remove_schedule_cost_change(user, schedule, departments, business_data,
                                calendar_date):
    """Calculate cost differential to departments if deleting schedule.
    
    This function recalcuates the workweek costs of the employee assigned
    to the schedule being deleted. This is because the cost of schedules is
    sequential and not independent, thus we must recalculate the cost of the
    workweek for the employee with and without the schedule that will be
    deleted.
    
    In rare cases a schedule lands in 2 different workweeks. For example, a
    a late night shift on a saturday night where the beginning of a workweek
    is at midnight on sunday. Therefore this function will calculate both
    workweek cost changes in that case.
    
    Args:
        user: django authenticated user
        schedule: The schedule that will be deleted from the database.
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user
        calendar_date: Datetime date containing month and year of calendar
            that the user has removed schedule from.
    Returns:
        A dictionary of departments that map to the change in cost to the 
        various departments. 
    """

    # Create dict for department costs
    department_costs = {}
    for department in departments:
        department_costs[department.id] = {'name': department.name, 'cost': 0}
    department_costs['total'] = {'name': 'total', 'cost': 0}
    
    # Get workweeks schedule intersects with schedule
    workweek_times_list = [get_start_end_of_weekday(schedule.start_datetime, user)]
    if schedule.end_datetime > workweek_times_list[0]['end']:
        second_workweek = get_start_end_of_weekday(schedule.end_datetime, user)
        workweek_times_list.append(second_workweek)
        
    total_new_cost = {}
    
    # For each workweek schedule intersects with, calculate cost difference
    for workweek_times in workweek_times_list:
        # Calculate old workweek costs before deletion
        workweek_schedules = (Schedule.objects.select_related('department', 'employee')
                                      .filter(user=user,
                                              end_datetime__gt=workweek_times['start'],
                                              start_datetime__lt=workweek_times['end'],
                                              employee=schedule.employee)
                                      .order_by('start_datetime', 'end_datetime'))                                        
        old_cost = single_employee_costs(workweek_times['start'], workweek_times['end'],
                                         schedule.employee, workweek_schedules, 
                                         departments, business_data, 
                                         calendar_date.month, calendar_date.year)
                                                                                           
        # Remove schedule to be deleted and recalculate new workweek cost
        new_workweek_schedules = workweek_schedules.exclude(pk=schedule.id)
        new_cost = single_employee_costs(workweek_times['start'], workweek_times['end'],
                                         schedule.employee, new_workweek_schedules, 
                                         departments, business_data, 
                                         calendar_date.month, calendar_date.year)
                                               
        # Calculate difference between old and new costs
        for dep in new_cost:
          old_department_cost = old_cost[dep]
          new_department_cost = new_cost[dep]
          new_cost[dep] = new_department_cost - old_department_cost
          
        # Add up different workweek cost changes
        if not total_new_cost:
            total_new_cost = new_cost
        else: # If 2 workweeks, combine cost difference of the 2 workweeks
            for dep in new_cost:
              total_new_cost[dep] += new_cost[dep]
            
    return total_new_cost
    
    
def add_employee_cost_change(user, schedule, new_employee, departments, 
                             business_data, calendar_date):
    """Calculate cost differential to departments if assigning employee
    
    This function recalcuates the workweek costs of the employee assigned
    to the schedule and if an employee is already assigned, the cost change of
    removing the old employee from the schedule. 
    
    In rare cases a schedule lands in 2 different workweeks. For example, a
    a late night shift on a saturday night where the beginning of a workweek
    is at midnight on sunday. Therefore this function will calculate both
    workweek cost changes in that case.
    
    Args:
        user: django authenticated user
        schedule: The schedule that will be deleted from the database.
        new_employee: django employee model of employee that will be assigned
          to the schedule.
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user
        calendar_date: Datetime date containing month and year of calendar
            that the user has removed schedule from.
    Returns:
        A dictionary of departments that map to the change in cost to the 
        various departments. 
    """
    
    department_costs = {} # Create dict for department costs
    for department in departments:
        department_costs[department.id] = {'name': department.name, 'cost': 0}
    department_costs['total'] = {'name': 'total', 'cost': 0}         
    
    # Get workweeks that intersect with schedule
    workweek_times_list = [get_start_end_of_weekday(schedule.start_datetime, user)]
    if schedule.end_datetime > workweek_times_list[0]['end']:
        second_workweek = get_start_end_of_weekday(schedule.end_datetime, user)
        workweek_times_list.append(second_workweek)
        
    employees = [new_employee] # Employee list used for query
    if schedule.employee:
        employees.append(schedule.employee)
    total_new_cost = {}
    
    # For each workweek schedule intersects with, calculate cost difference
    for workweek_times in workweek_times_list:
        # Calculate old workweek costs before deletion
        workweek_schedules = (Schedule.objects.select_related('department', 'employee')
                                      .filter(user=user,
                                              end_datetime__gt=workweek_times['start'],
                                              start_datetime__lt=workweek_times['end'],
                                              employee__in=employees)
                                      .order_by('start_datetime', 'end_datetime')) 
        # Get old workweek costs before employee assignment
        new_employee_schedules = [sch for sch in workweek_schedules if sch.employee == new_employee]
        old_cost = single_employee_costs(workweek_times['start'], 
                                         workweek_times['end'],
                                         new_employee, new_employee_schedules, 
                                         departments, business_data, 
                                         calendar_date.month,
                                         calendar_date.year)
        # Get new workweek costs after employee assignment  
        bisect.insort_left(new_employee_schedules, schedule)
        new_cost = single_employee_costs(workweek_times['start'], 
                                         workweek_times['end'],
                                         new_employee, new_employee_schedules, 
                                         departments, business_data, 
                                         calendar_date.month,
                                         calendar_date.year)
                                         
        if schedule.employee: # Calculate changes to unassigning employee
            old_employee_schedules = [sch for sch in workweek_schedules if sch.employee == schedule.employee]
            old_emp_old_cost = single_employee_costs(workweek_times['start'], 
                                                     workweek_times['end'],
                                                     schedule.employee, 
                                                     old_employee_schedules, 
                                                     departments, business_data, 
                                                     calendar_date.month, 
                                                     calendar_date.year)
            for dep in old_cost:
                old_cost[dep] += old_emp_old_cost[dep]
            # Get new workweek costs after removing employee from schedule
            old_employee_schedules.remove(schedule)
            old_emp_new_cost = single_employee_costs(workweek_times['start'], 
                                                     workweek_times['end'],
                                                     schedule.employee, 
                                                     old_employee_schedules, 
                                                     departments, business_data, 
                                                     calendar_date.month, 
                                                     calendar_date.year)
            for dep in new_cost:
                new_cost[dep] += old_emp_new_cost[dep]    
                                                                     
        # Calculate difference between old and new costs
        for dep in new_cost:
          old_department_cost = old_cost[dep]
          new_department_cost = new_cost[dep]
          new_cost[dep] = new_department_cost - old_department_cost
          
        # Add up different workweek cost changes
        if not total_new_cost:
            total_new_cost = new_cost
        else: # If 2 workweeks, combine cost difference of the 2 workweeks
            for dep in new_cost:
              total_new_cost[dep] += new_cost[dep]

    return total_new_cost
      
    
def single_employee_costs(start_dt, end_dt, employee, schedules, departments, 
                          business_data, month=None, year=None):
    """Calculate costs of employee given workweek and schedules.
    
    This function is simply a helper functio that combines the various
    functions used to calculate the cost of schedules with respect to a
    workweek.
    
    
    Args:
        start_dt: Python datetime representing start of workweek.
        end_dt: Python datetime representing end of workweek.
        employee: employee of schedules to calculate cost with.
        schedules: schedules of employee in workweek.
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user
        month: integer value of month. If value present, this function
            calculates schedules that only have overlapping time in the month.
            (Since often workweeks at start/end of month have days that are
            outside that month.)
        year: integer value of year. Optional value similar to month.
    Returns:
        A dict containing cost of employing employee for a given workweek for
        all departments of managing user.
    """
    
    workweek_hours = workweek_hours_detailed(start_dt, end_dt, departments, 
                                             business_data, schedules, 
                                             month, year)
    workweek_hours_dict = {employee: workweek_hours}
    
    if month and year:
        month_only = True
    else:
        month_only = False
    
    workweek_costs = calculate_workweek_costs(workweek_hours_dict, 
                                              departments, business_data,
                                              month_only)             
    return workweek_costs
    
    
    
                          
                          
                          
                          
                          
