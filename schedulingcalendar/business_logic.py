"""
Author: Ryan Johnson

Python module containing business logic. Functions for processing eligability
of employees and getting employee availability for a given schedule are
contained here.
"""

from datetime import datetime, timedelta
from operator import itemgetter
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from .models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence)
import json


def get_eligables(schedule):
    """Return a sorted list of eligable employee's along with info.
    
    The eligable list is a sorted list of employees, a dictionary
    containing any potential conflicts the eligable employee has relative to
    the schedule, and a tuple of integers that represents multiple criterion 
    for sorting their 'eligability'.
    
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
        desired_times_score = _calculate_desired_times_score(employee)
        desired_hours_score = _calculate_desired_hours_score(availability,
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
    the sum of all the lesser conflicts + 1
    
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
    
    
def _calculate_desired_times_score(employee):
    """Calculate if schedule has overlap with employee desired working time.
    
    Employee's are able to set days and hours that they would prefer to work.
    If a schedule overlaps with these desired times, the employee is more
    eligable for the schedule than those who don't have overlapping desired
    time. Mathematically this is represented by returnning 2 if no overlaps, 
    returnning 1 if there are overlaps but not entirely, and return 0 if 
    desired time is contained within schedule time duration.
    
    Args:
        employee: Employee model object.
    Returns:
        Integer score of overlap of desired time with schedule's interval of 
        time. A lower score means more overlap.
    """
    
    return 2
    
    
def _calculate_desired_hours_score(availability, employee):
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
        availability: The availability dict containing conflict information.
        employee: Django Employee model.
    Returns:
        Integer score of absolute difference between current scheduled hours 
        and employee's desired amount of hours per week.
    """
    
    return availability['Hours Scheduled'] - employee.desired_hours
    
    
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
           
    # Get unavailabilities employee is assigned to that overlap with schedule
    sch_weekday = schedule.start_datetime.weekday()
    start_time = schedule.start_datetime.time()
    end_time = schedule.end_datetime.time()
    unav_repeat = (RepeatUnavailability.objects.filter(employee=employee.id,
                                                       weekday=sch_weekday,
                                                       start_time__lt=end_time,
                                                       end_time__gt=start_time))
    availability['(U)'] = unav_repeat         

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
    
    curr_hours = calculate_weekly_hours(employee, schedule.start_datetime, schedule.user)
    return curr_hours + schedule_length(schedule)
    
    
def calculate_weekly_hours(employee, dt, user):
    """Calculate # of hours employee works for workweek containing datetime."""
    #TODO: Not count time of schedules that overlap with 2 different workweeks
    #TODO: Not double count schedules that overlap in time
    workweek_datetimes = get_start_end_of_weekday(dt, user)
    schedules = (Schedule.objects.filter(user=user,
                                         employee=employee,
                                         start_datetime__gte=workweek_datetimes['start'],
                                         start_datetime__lt=workweek_datetimes['end']))
                                         
    hours = 0
    
    for schedule in schedules:
        hours += schedule_length(schedule)
    
    return hours
    
    
def get_start_end_of_weekday(dt, user):
    """Return start and end datetimes of workweek that contain datetime inside
    
    Because users are allowed to pick a specific day and time for the start
    of the workweek, one cannot assume the workweek will start on a monday at
    12:00 am. In order to calculate the start datetime of a workweek, we first
    find the start date relative to some date that must be contained within 
    the workweek
    """
    
    # TODO: we should get business data by user, not pk
    business_data = BusinessData.objects.get(user=user, pk=1)
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
    
    start_datetime_of_week = datetime.combine(start_date_of_week, start_time_of_week)
    end_datetime_of_week = start_datetime_of_week + timedelta(7)
    
    return {'start': start_datetime_of_week, 'end': end_datetime_of_week}
    
    
    
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
    
    MODEL_CONFLICTS = ('(S)', '(V)', '(A)', '(U)')
    avail_serialized = {}
    
    for key in MODEL_CONFLICTS:
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
        
        
def schedule_length(schedule):
    """Calculate length of a schedule
    
    Args:
        schedule: django schedule object.
    Returns:
        A float representing number of hours of schedule length.
    """
    time_delta = schedule.end_datetime - schedule.start_datetime
    hours = time_delta.seconds / 3600
    return hours
    
        
def schedule_cost(schedule):
    """Calculate cost of schedule.
    
    Args:
        schedule: django schedule object.
    Returns:
        Float number representing wage cost of schedule. (Note: this does not
        factor in the total cost of benefits of assigned employee.)
    """
    
    if schedule.employee == None:
        return 0
            
    hours = schedule_length(schedule)
    return hours * schedule.employee.wage
    
    
def schedules_collection_cost(schedules):
    """Calculate wage cost of a collection of schedules
    
    Args:
        schedules: django queryset containing schedules object.
        duration: 
    Returns:
        Float number representing sum of all schedules wage costs. (Note: this
        does not factor in the total cost of benefits of assigned employee.)
    """
    
    sum = 0
    
    for schedule in schedules:
        sum += schedule_cost(schedule)
    
    return sum
    
    
def non_wage_monthly_benefits_costs(user, month, year, department):
    """Calculate the cost of benefits for a given calendar."""
    return 0
    
    
def calendar_cost(user, month, year, department):
    """Calculate cost of given calendar of schedules, including benefits.
    
    Args:
        user: django authenticated user
        month: integer value of month
        year: integer value of year
        department: django department model object
    Returns:
        float value of the total cost of a given month for a given department,
        including cost of wages and all benefits such as medical and social
        security.
    """

    schedules = (Schedule.objects.select_related('employee')
                                 .filter(user=user,
                                         start_datetime__month=month,
                                         start_datetime__year=year,
                                         department=department))
                                         
    wage_cost = schedules_collection_cost(schedules)
    non_wage_benefits_cost = non_wage_monthly_benefits_costs(user, month, year, department)
    
    return wage_cost + non_wage_benefits_cost
    

def all_calendar_costs(user, month, year):
    """Calculate cost of given calendar of schedules, including benefits.
    
    Args:
        user: django authenticated user
        month: integer value of month
        year: integer value of year
    Returns:
        calendar_costs: a list of dictionaries, the dictionaries contain the
        department's id, name, and the float value of the absolute cost for
        that month (including benefits).
    """
    
    departments = Department.objects.filter(user=user)
    calendar_costs = []
    total_sum = 0
    
    for department in departments:
        cost = calendar_cost(user, month, year, department)
        total_sum += cost
        dep_cost = {'id': department.id, 'name': department.name, 'cost': cost}
        calendar_costs.append(dep_cost)
        
    # We also keep track of the total sum of all calendars for the user
    total = {'id': 'all', 'name': 'Total', 'cost': total_sum}
    calendar_costs.append(total)
        
    return calendar_costs
    
    
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
 