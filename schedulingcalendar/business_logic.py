from operator import itemgetter
from .models import (Schedule, Department, DepartmentMembership, 
                     Employee, Vacation, RepeatUnavailability)
from django.forms.models import model_to_dict
import json
import datetime


"""
So this True Eligables (TM)........function will basically fill the gaps
that the original one didnt. I think that is a couple of things. So what do
we want to return?
"""

def get_eligables(schedule_pk):
    """Returns a sorted list of eligable employee pk's along with info.
    
    
    The next tier down will sort all sublists created by its parent tier
    Tier 1 Sort: A, O, U, V, S
    Tier 2 Sort: Priority of department
    Tier 3 Sort: Desired time sort (Depending on user desire...)
    Tier 4 Sort: Desired hour sort (Push employees over it down, push employees
                                    under it up)
    """
    # Get schedule and department members
    schedule = Schedule.objects.get(pk=schedule_pk)
    eligables = []
    dep_membership = DepartmentMembership.objects.filter(department=schedule.department)
    # get employee availability and its sorting score
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
                         
        eligables.append((employee, availability, sorting_score))
    
    eligables.sort(key=lambda e: e[2])
    print "-----------------------------------------------------------"
    print ""
    print "ELIGABLES IN get_eligables FUNCTION IS:"
    for e in eligables:
      print e
      print ""
    print ""
    print "-----------------------------------------------------------"
    return {'schedule': schedule, 'eligables': eligables}
    
    
def _calculate_availability_score(availability):
    """Calculate availability of employee given conflicts.
        
    S = 8, V = 4, U = 2, O = 1
        
    The score for each availability tier is greater than the sum of all
    lesser conflicts combined. This ensures that a combination of lesser
    conflicts does not override a larger, more serious conflict.
    
    Mathematically this means that the next level of conflict's score will be
    the sum of all the lesser conflicts + 1
    """
    score = 0
    if availability['(S)']: score += 8
    if availability['(V)']: score += 4
    if availability['(U)']: score += 2
    if availability['(O)']: score += 1
    return score
    
    
def _calculate_dep_priority_score(dep_member):
    """
    Sort list by priority of department for employee, 0 means main department,
    thus employees with 0 will be at beginning of list.
    """
    return dep_member.priority
    
    
def _calculate_desired_times_score(employee):
    """
    Query desired times in employee. Return 2 if no overlaps, return 1 if 
    overlaps but not entirely, and return 0 if desired time is contained within
    schedule time duration.
    """
    return 2
    
    
def _calculate_desired_hours_score(availability, employee):
    """
    Calculate the differential between current_hours_assigned - desired_hours
    to employee. The list is sorted with smallest differential at 0th index,
    largest differential at end of index.
    """
    return availability['Hours Scheduled'] - employee.desired_hours
    
    
def get_availability(employee, schedule):
    """
    According to new availability, an available employee is one where
    all the elements except O are empty...
        
    Add: hourly flag, Overtime flag should be calculated here    
    """
    
    availability = {'(S)': [], '(V)': [], '(U)': [], '(O)': False,
                    'Hours Scheduled': 0}
    # Get schedules, vacations, and unavailabilities employee is assigned to
    schedules = (Schedule.objects.filter(employee=employee.id)
                                 .exclude(pk=schedule.pk))
    print "-----------------------------------------------------------"
    print ""
    print "SCHEDULE ID IN get_availability FUNCTION IS:"
    print schedule.id
    print "For employee: "
    print employee
    print
    for s in schedules:
      print s.id
      print ""
    print ""
    print "-----------------------------------------------------------"
    vacations = Vacation.objects.filter(employee=employee.id)
    sch_weekday = schedule.start_datetime.weekday()
    unav_repeat = RepeatUnavailability.objects.filter(employee=employee.id,
                                                      weekday=sch_weekday)

    # Check for schedule conflict    
    for s in schedules:
        if schedule.start_datetime < s.end_datetime and s.start_datetime < schedule.end_datetime:
            availability['(S)'].append(s)
    # Check for vacation conflict          
    for v in vacations:
        if schedule.start_datetime < v.end_datetime and v.start_datetime < schedule.end_datetime:
            availability['(V)'].append(v)
    # Check for repeating unavailability conflict        
    for unav in unav_repeat:
        start_time = schedule.start_datetime.time()
        end_time = schedule.end_datetime.time()
        if start_time < unav.end_time and unav.start_time < end_time:
            availability['(U)'].append(unav)
    # Check current hours worked for later evaluation of overtime       
    hours_curr_worked = calculate_weekly_hours(employee)
    availability['Hours Scheduled'] = hours_curr_worked
    availability['(O)'] = False
            
    return availability
    
    
    
def calculate_weekly_hours(employee):
        return 0
        # WorkWeek.objects.all()... Use this to determine beginning of workweek
        # All schedules that have any overlap with this will have to be appended
    
    
def get_eligable_info(employee_availability):
    """Given employee availability dict, return string descriptions."""
    pass
    
    
def eligable_list_to_dict(eligable_list):
    MODEL_CONFLICTS = ('(S)', '(V)', '(U)')
    eligable_serialized_list = []
    
    for e in eligable_list['eligables']:
        eligable_serialized = []
        
        employee_serialized = model_to_dict(e[0])
        eligable_serialized.append(employee_serialized)
        
        # Serialize the models contained in the availability conflict dict
        avail_serialized = {}
        for key in MODEL_CONFLICTS:
            serialized_conflicts = []
            for conflict in e[1][key]: # e[1] is the availability dictionary
                serial_conf = model_to_dict(conflict)
                serialized_conflicts.append(serial_conf)
            avail_serialized[key] = serialized_conflicts
        avail_serialized['(O)'] = e[1]['(O)']
        avail_serialized['Hours Scheduled'] = e[1]['Hours Scheduled']
        
        eligable_serialized.append(avail_serialized)
        eligable_serialized_list.append(eligable_serialized)
        
    # Serialize the corresponding schedule
    serialized_schedule = model_to_dict(eligable_list['schedule'])
    
    data = {'schedule': serialized_schedule, 
            'eligable_list': eligable_serialized_list}
    return data
    
    
def date_handler(obj):
    """
    Anthony Hatchkins: http://stackoverflow.com/questions/23285558/datetime-date2014-4-25-is-not-json-serializable-in-django
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