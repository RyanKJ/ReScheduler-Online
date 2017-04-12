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
from .models import (Schedule, Department, DepartmentMembership, 
                     Employee, Vacation, RepeatUnavailability)
import json


def get_eligables(schedule):
    """Return a sorted list of eligable employee pk's along with info.
    
    The eligable list is a sorted list of employee primary keys, a dictionary
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
        
    S = 8, V = 4, U = 2, O = 1
        
    The score for each availability tier is greater than the sum of all
    lesser conflicts combined. This ensures that a combination of lesser
    conflicts does not override a larger, more serious conflict.
    
    Mathematically this means that the next level of conflict's score will be
    the sum of all the lesser conflicts + 1
    
    Args:
      availability: The availability dict containing conflict information.
    Returns:
      score: aAn integer value of conflict. Higher score means more conflicts.
    """
    
    score = 0
    
    if availability['(S)']: score += 8
    if availability['(V)']: score += 4
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
    hours_curr_worked = calculate_weekly_hours(employee, schedule)
    availability['Hours Scheduled'] = hours_curr_worked
    availability['(O)'] = False
            
    return availability
    
    
def calculate_weekly_hours(employee, schedule):
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
    
    return 0
    
    
def eligable_list_to_dict(eligable_list):
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
    MODEL_CONFLICTS = ('(S)', '(V)', '(U)')
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
    """
    Add converting instructions to JSON parser for datetime objects. 
    
    Written by Anthony Hatchkins: 
    http://stackoverflow.com/questions/23285558/datetime-date2014-4-25-is-not-json-serializable-in-django
    """
    
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError
        
        
def yearify(curr_year, n):
    """Return a string list of n+5 years starting 4 years before curr_year.
    
    Args:
        curr_year: string representation of present year
        n: number of years after present year desired to be in list
    """
        
    year_list = []
    start_year = int(curr_year) - 4
    
    for i in range(start_year, start_year + n + 5):
        year_list.append(str(i))
           
    return year_list