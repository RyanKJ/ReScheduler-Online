import json
import bisect
import calendar
from datetime import date, datetime, timedelta, time
from operator import itemgetter
from django.utils import timezone
from django.contrib.auth.models import User
from .time_logic import calculate_weekly_hours, time_dur_in_hours, get_start_end_of_weekday
from ..models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime, LiveSchedule, LiveCalendar,
                     LiveCalendarDepartmentViewRights, LiveCalendarEmployeeViewRights)
                     
 

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
     

def all_calendar_hours_and_costs(user, departments, schedules, employees, 
                                 month, year, business_data, single_workweek=None):
    """Calculate hours cost of given month of schedules, including benefits.
    
    This function keeps track of the regular hours, overtime hours, benefits
    cost that depend on hours worked and monthly recurring benefits cost for 
    schedules, days, workweeks, and months.
    
    Args:
        user: Django authenticated user.
        departments: All departments for user.
        schedules: All schedules for the user for the given calendar view.
        employees: All employees belonging to user
        month: Integer value of month.
        year: Integer value of year.
        business_data: Business settings the user has.
        single_workweek: Optional single workweek, if exists, this overrides
          calculating all workweeks for the month. This also assumes the 
          supplied schedules argument consists of schedules that only belong 
          to this single workweek.
    Returns:
        A dict containing the hours and costs of schedules, days, workweeks,
        and month for every department the user has.
    """  
    
    hours_and_costs = {'schedule_hours_costs': {}, 'day_hours_costs': {}, 
                       'workweek_hours_costs': [], 'month_costs': {}}
    workweeks = []
   
    if single_workweek:
        single_workweek['schedules'] = schedules
        workweeks.append(single_workweek)
    else:
        # Get all workweeks with any intersection with month
        beginning_of_month = timezone.make_aware(datetime(year, month, 1, 1))
        first_workweek = get_start_end_of_weekday(beginning_of_month, user)
        first_workweek['schedules'] = []
        workweeks.append(first_workweek)
        for i in range(1, 6):
            ith_day = first_workweek['start'] + timedelta((i * 7) + 1)
            ith_workweek = get_start_end_of_weekday(ith_day, user)
            ith_workweek['schedules'] = []
            # If start of workweek is contained in month, add workweek
            if ith_workweek['start'].month == month:
                workweeks.append(ith_workweek)
            
        # Filter out employeeless schedules then append schedules to the workweek they belong to
        schedules = [sch for sch in schedules if sch.employee]
        for sch in schedules:
            for workweek in workweeks:
                if sch.start_datetime >= workweek['start'] and sch.start_datetime <= workweek['end']:
                    workweek['schedules'].append(sch)
                    break
                
    # Create department dicts for monthly costs
    for department in departments:
        hours_and_costs['month_costs'][department.id] = {'name': department.name, 'cost': 0}
    hours_and_costs['month_costs']['total'] = {'name': 'Total', 'cost': 0}
            
    # Sum up costs for each workweek and add to department costs
    for workweek in workweeks:
        employee_hours = all_employee_hours(user, workweek['start'], workweek['end'], 
                                            workweek['schedules'], departments, business_data, 
                                            month, year)
        # Calculate schedule costs
        # Disabled for speed, will enable if user wants schedule hour info functionality.
        #calculate_schedule_costs(employee_hours, hours_and_costs['schedule_hours_costs'], business_data)
        
        # Calculate day costs
        day_costs = calculate_day_costs(employee_hours, departments, business_data)
        hours_and_costs['day_hours_costs'].update(day_costs)
        
        # Calculate workweek costs
        workweek_costs = calculate_workweek_costs(employee_hours, departments, business_data, False)
        workweek_times = {'start': workweek['start'].isoformat(), 'end': workweek['end'].isoformat()}
        hours_and_costs['workweek_hours_costs'].append({'date_range': workweek_times, 'hours_cost': workweek_costs})
            
        # Calculate month costs
        workweek_costs_month = calculate_workweek_costs(employee_hours, departments, business_data, True)
        for dep_id in workweek_costs_month:
            hours_and_costs['month_costs'][dep_id]['cost'] += workweek_costs_month[dep_id]['cost']
            
                
    # Calculate month costs
    total_monthly_benefits = 0 # Get monthly benefits cost
    monthly_benefits_per_dep = 0
    for employee in employees:
        total_monthly_benefits += employee.monthly_medical
    monthly_benefits_per_dep = total_monthly_benefits / (len(hours_and_costs['month_costs']) - 1)
    
    for dep_id in hours_and_costs['month_costs']:
        if dep_id == 'total':
            hours_and_costs['month_costs'][dep_id]['cost'] += total_monthly_benefits
        else:
            hours_and_costs['month_costs'][dep_id]['cost'] += monthly_benefits_per_dep

    return hours_and_costs
    
 
def all_employee_hours(user, week_start, week_end, schedules, departments, business_data, 
                       month=None, year=None):
    """Return a dict containing working hours of all employees in a workweek.
    
    A workweek is defined as the start and end datetimes of a workweek. Since
    an employer can determine the start day and time of a workweek, workweeks
    are arbitrary with respect to employer. This function returns a dict
    containing employee django models as keys and their hours worked as values.
    
    The hours worked is returned by a helper function, employee_hours_detailed,
    and each hour value is a dict containing hour information for the employee
    organized by each schedule, each day the schedule belongs to, and the 
    workweek itself.
    
    Args:
        user: django authenticated user
        week_start: Python datetime representing start of workweek
        week_end: Python datetime representing end of workweek
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
    
    employee_hours = {}
                                            
    # Sort schedules by employee        
    for schedule in schedules:
        if schedule.employee not in employee_hours:
            employee_hours[schedule.employee] = []
        employee_hours[schedule.employee].append(schedule)
    
    # For each employee, get hours for each schedule, day, and week
    for employee in employee_hours:
        hours = employee_hours_detailed(week_start, week_end, employee, departments,
                                        business_data, employee_hours[employee],
                                        month, year)
        employee_hours[employee] = hours
        
    return employee_hours
    
    
def employee_hours_detailed(workweek_start_dt, workweek_end_dt, employee, 
                            departments, business_data, schedules, 
                            month=None, year=None):
    """Calculate the number of hours and overtime hours for given schedules
    as they occur chronologically and according to which department those 
    hours and overtime hours occur.
    
    This function works similarly to calculate_weekly_hours in that it does
    not count time overlapping between multiple schedules for one employee as
    different times. So we ensure we do not count time where employee is 
    present at work for a day in 2 different departments twice. The first
    occuring schedule is the department whose hours are counted in the case of
    an overlap.
    
    Then we count the number of hours the employee is working both in that 
    department and overall all departments for that workweek. Furthermore, 
    since we are interested in the ratio of employment costs to average monthly 
    revenue, we keep a running sum of the regular and overtime hours of schedules
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
    
    Also: Calculating the hours is a convoluted mess because calculating the 
    cost of a schedule is dependent on 2 different variables: overtime caused 
    by previous schedules for that given workweek AND where the overtime hours 
    occur given that an employee can belong to more than one department. For 
    example, employee A belongs to department 1 and 2 and overtime occurs at 
    40 hours. Employee A works 30 hours in the beginning of the workweek in 
    department 1 then 20 hours in department 2. 10 of those hours are overtime,
    but they occur in a different department. This means we must keep track of
    the hours worked by an employee in a work week across departments to 
    correctly attribute which overtime hour belongs to which department,
    otherwise the cost for a given department's schedules for that month will
    be incorrect.
    
    Args:
        workweek_start_dt: Python datetime representing start of workweek
        workweek_end_dt: Python datetime representing end of workweek
        employee: Employee model instance who's hours we are calculating for the week
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
        A dict containing the number of non-overtime hours and overtime hours
        for individual schedules, each day in the workweek, and the overall
        workweek itself. Also, for the weekly hours, there is a hours only 
        in month for calculating strictly month costs as well.
    """
                     
    # Create hours dict to keep track of hours for each department
    overtime = business_data.overtime
    min_time_for_break = employee.min_time_for_break
    break_time_min = employee.break_time_in_min
    
    schedule_hours = {}
    day_hours = {}
    week_hours = {}
    
    # Get all dates within workweek
    for i in range(0, 7):
        date = workweek_start_dt.date() + timedelta(i)
        day_hours[date] = {}
    
    # Create dicts containing hour information for each week and individual day
    for dep in departments:
        week_hours[dep.id] = {'hours': 0, 'overtime_hours': 0, 'hours_in_month': 0, 'ovr_t_in_month': 0}
        for date in day_hours:
            day_hours[date][dep.id] = {'hours': 0, 'overtime_hours': 0}  
    # Also create dicts containing hour information for total sum across departments
    week_hours['total'] = {'hours': 0, 'overtime_hours': 0, 'hours_in_month': 0, 'ovr_t_in_month': 0}
    for date in day_hours:
            day_hours[date]['total'] = {'hours': 0, 'overtime_hours': 0}
    
    # For each schedule calculate hours and overtime hours
    for schedule in schedules:
        schedule_duration = time_dur_in_hours(schedule.start_datetime, 
                                              schedule.end_datetime,
                                              None, None, min_time_for_break, 
                                              break_time_min)

        # Calculate hours in the workweek, first checking if adding the next
        # schedule's duration will put that employee's total workweek hours
        # into overtime, if so, calculate overtime hours as well.
        overall_non_overtime_hours = week_hours['total']['hours'] + schedule_duration
        if overall_non_overtime_hours > overtime:
            overtime_hours = overall_non_overtime_hours - overtime
            regular_hours = schedule_duration - overtime_hours
            
            # Save hour information for each individual schedule
            schedule_hours[schedule.id] = {'hours':regular_hours, 
                                           'overtime_hours': overtime_hours,
                                           'duration': schedule_duration}
            
            # Save hour information for each day
            day_hours[schedule.start_datetime.date()]['total']['hours'] += regular_hours
            day_hours[schedule.start_datetime.date()][schedule.department.id]['hours'] += regular_hours
            day_hours[schedule.start_datetime.date()]['total']['overtime_hours'] += overtime_hours
            day_hours[schedule.start_datetime.date()][schedule.department.id]['overtime_hours'] += overtime_hours
            
            # Save hour information for week
            week_hours['total']['hours'] += regular_hours
            week_hours[schedule.department.id]['hours'] += regular_hours
            week_hours['total']['overtime_hours'] += overtime_hours
            week_hours[schedule.department.id]['overtime_hours'] += overtime_hours
            
            # Save hour information for week only if schedule is strictly in month
            sch_month = schedule.start_datetime.month
            sch_year = schedule.start_datetime.year
            if sch_month == month and sch_year == year:
                week_hours['total']['hours_in_month'] += regular_hours
                week_hours[schedule.department.id]['hours_in_month'] += regular_hours
                week_hours['total']['ovr_t_in_month'] += overtime_hours
                week_hours[schedule.department.id]['ovr_t_in_month'] += overtime_hours
        else:
            # Save hour information for each individual schedule
            schedule_hours[schedule.id] = {'hours': schedule_duration, 
                                           'overtime_hours': 0,
                                           'duration': schedule_duration}
            
            # Save hour information for each day
            day_hours[schedule.start_datetime.date()]['total']['hours'] += schedule_duration
            day_hours[schedule.start_datetime.date()][schedule.department.id]['hours'] += schedule_duration
            
            # Save hour information for week
            week_hours['total']['hours'] += schedule_duration
            week_hours[schedule.department.id]['hours'] += schedule_duration
                
            # Save hour information for week only if schedule is strictly in month
            sch_month = schedule.start_datetime.month
            sch_year = schedule.start_datetime.year
            if sch_month == month and sch_year == year:
                week_hours['total']['hours_in_month'] += schedule_duration
                week_hours[schedule.department.id]['hours_in_month'] += schedule_duration

    return {'schedule_hours': schedule_hours, 'day_hours': day_hours, 'week_hours': week_hours}
    
    
def calculate_cost(regular_hours, overtime_hours, wage, 
                   overtime_multiplier, social_security):
    """Calculate the cost of the given hours and overtime.
    
    Args:
        regular_hours: Float value of regular, non-overtime hours.
        overtime_hours: Float value of overtime hours.
        wage: Float value to multiply hours by.
        overtime_multiplier: amount overtime multiplies by.
        social_security: Percentage of cost added to employer.
        
    Returns:
        A float representing total value of all costs.
    """
    
    regular_cost = regular_hours * wage
    over_t_cost = overtime_hours * wage * overtime_multiplier
    total_pre_ss = regular_cost + over_t_cost
    total = total_pre_ss + (total_pre_ss * (social_security / 100))
    
    return total
    
    
def calculate_workweek_costs(hours, departments, business_data, month_only=False):
    """Calculate the costs of the workweek.
    
    Args:
        hours: Dict of employees and their hours in that workweek.
        departments: List of all departments for managing user.
        business_data: Django model of business data for managing user
        month_only: Boolean to determine if to count all of the workweek costs
            or only days in the workweek that overlap with the month.
    Returns:
        A dict of key values mapping department to float number costs in
        dollars and total regular and overtime hours for that department.
    """
    # TODO: Add hourly associated benefits cost like social security, workmans comp
    ovr_t_multiplier = business_data.overtime_multiplier
    workweek_costs = {}
    
    for department in departments:
        workweek_costs[department.id] = {'hours': 0, 'overtime_hours': 0, 'cost': 0}
    workweek_costs['total'] = {'hours': 0, 'overtime_hours': 0, 'cost': 0}
    
    for employee in hours:
        week_hours = hours[employee]['week_hours']
        for department in week_hours:
            if month_only:
                regular_hours = week_hours[department]['hours_in_month']
                overtime_hours = week_hours[department]['ovr_t_in_month']
                cost = calculate_cost(regular_hours, overtime_hours, employee.wage, 
                                      ovr_t_multiplier, employee.social_security)
            else:
                regular_hours = week_hours[department]['hours']
                overtime_hours = week_hours[department]['overtime_hours']
                cost = calculate_cost(regular_hours, overtime_hours, employee.wage, 
                                      ovr_t_multiplier, employee.social_security)
                
            workweek_costs[department]['hours'] += regular_hours
            workweek_costs[department]['overtime_hours'] += overtime_hours
            workweek_costs[department]['cost'] += cost
        
    return workweek_costs 
    

def calculate_day_costs(hours, departments, business_data):  
    """Calculate the costs of each day in the workweek.
    
    Args:
        hours: Dict of employees and their hours in that workweek.
        departments: List of all departments for managing user.
        business_data: Django model of business data for managing user
    Returns:
        A dict of dates in iso formatm mapping to the hours and 
        costs for that day.
    """
    # TODO: Add hourly associated benefits cost like social security, workmans comp
    ovr_t_multiplier = business_data.overtime_multiplier
    day_costs_for_week = {}
    
    for employee in hours:
        day_hours_for_week = hours[employee]['day_hours']
        for date in day_hours_for_week:
            # If we have not seen the date before, set day_cost[date] = day_hours_for_week[date]
            if not date.isoformat() in day_costs_for_week:
                for dep in day_hours_for_week[date]:
                    regular_hours = day_hours_for_week[date][dep]['hours']
                    overtime_hours = day_hours_for_week[date][dep]['overtime_hours']
                    cost = calculate_cost(regular_hours, overtime_hours, employee.wage, 
                                      ovr_t_multiplier, employee.social_security)
                    day_hours_for_week[date][dep]['cost'] = cost
                day_costs_for_week[date.isoformat()] = day_hours_for_week[date]
            else:
                day_cost = day_costs_for_week[date.isoformat()]
                for dep in day_cost:
                  regular_hours = day_hours_for_week[date][dep]['hours']
                  overtime_hours = day_hours_for_week[date][dep]['overtime_hours']
                  cost = calculate_cost(regular_hours, overtime_hours, employee.wage, 
                                      ovr_t_multiplier, employee.social_security)
                        
                  day_cost[dep]['hours'] += regular_hours
                  day_cost[dep]['overtime_hours'] += overtime_hours
                  day_cost[dep]['cost'] += cost
                  
    return day_costs_for_week
          

def calculate_schedule_costs(hours, all_schedule_hours_dicts, business_data): 
    """Calculate the costs of each schedule.
    
    Args:
        hours: Dict of employees and their hours in that workweek.
        all_schedule_hours_dicts: Final dict product containing all hours
          and cost information for the particular calendar.
        business_data: Django model of business data for managing user
    """

    # TODO: Add hourly associated benefits cost like social security, workmans comp
    ovr_t_multiplier = business_data.overtime_multiplier

    for employee in hours:
        schedule_hours = hours[employee]['schedule_hours']
        for schedule_id in schedule_hours:
            cost = calculate_cost(regular_hours, overtime_hours, employee.wage, 
                                      ovr_t_multiplier, employee.social_security)
            schedule_hours[schedule_id]['cost'] = cost
        # Update master dict containing all schedule hours and costs
        all_schedule_hours_dicts.update(hours[employee]['schedule_hours'])
    return
    

def remove_schedule_cost_change(user, schedule, departments, business_data,
                                calendar_date):
    """Calculate cost differential to departments if deleting schedule.
    
    This function recalcuates the workweek costs of the employee assigned
    to the schedule being deleted. This is because the cost of schedules is
    sequential and not independent, thus we must recalculate the cost of the
    workweek for the employee with and without the schedule that will be
    deleted.
    
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
    
    # Get the workweek that the schedule intersects with and workweek schedules
    workweek = get_start_end_of_weekday(schedule.start_datetime, user)
    workweek_schedules = (Schedule.objects.select_related('department', 'employee')
                                  .filter(user=user,
                                          end_datetime__gt=workweek['start'],
                                          start_datetime__lt=workweek['end'],
                                          employee=schedule.employee)
                                  .order_by('start_datetime', 'end_datetime')) 

    # Get old week hours and costs                   
    old_hours_cost = single_employee_costs(workweek['start'], workweek['end'],
                                           schedule.employee, workweek_schedules, 
                                           departments, business_data, 
                                           calendar_date.month, calendar_date.year)
                                                                                                 
    # Get new week (Old week minus schedule) hours and costs
    new_workweek_schedules = workweek_schedules.exclude(pk=schedule.id)
    new_hours_cost = single_employee_costs(workweek['start'], workweek['end'],
                                           schedule.employee, new_workweek_schedules, 
                                           departments, business_data, 
                                           calendar_date.month, calendar_date.year)

    # Calculate difference between old and new day hours/costs
    hours_cost_delta = calculate_cost_delta(old_hours_cost, new_hours_cost, 'subtract')
    
    return hours_cost_delta
    
    
def add_employee_cost_change(user, schedule, new_employee, departments, 
                             business_data, calendar_date):
    """Calculate cost differential to departments if assigning employee
    
    This function recalcuates the workweek costs of the employee assigned
    to the schedule and if an employee is already assigned, the cost change of
    removing the old employee from the schedule. 
    
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
     
    employees = [new_employee] # Employee list used for query
    if schedule.employee:
        employees.append(schedule.employee)
    workweek = get_start_end_of_weekday(schedule.start_datetime, user)
    workweek_schedules = (Schedule.objects.select_related('department', 'employee')
                                  .filter(user=user,
                                          end_datetime__gt=workweek['start'],
                                          start_datetime__lt=workweek['end'],
                                          employee__in=employees)
                                  .order_by('start_datetime', 'end_datetime')) 
     
    # Get old workweek costs before employee assignment
    new_employee_schedules = [sch for sch in workweek_schedules if sch.employee == new_employee]
    old_hours_cost = single_employee_costs(workweek['start'], 
                                     workweek['end'],
                                     new_employee, new_employee_schedules, 
                                     departments, business_data, 
                                     calendar_date.month,
                                     calendar_date.year)
    # Get new workweek costs after employee assignment  
    bisect.insort_left(new_employee_schedules, schedule)
    new_hours_cost = single_employee_costs(workweek['start'], 
                                     workweek['end'],
                                     new_employee, new_employee_schedules, 
                                     departments, business_data, 
                                     calendar_date.month,
                                     calendar_date.year)
                                     
    # Calculate difference between old and new day hours/costs for new employee
    hours_cost_delta = calculate_cost_delta(old_hours_cost, new_hours_cost, 'subtract')
                         
    # if another employee was already assigned to schedule previously, calculate cost diff                                 
    if schedule.employee:
        prev_employee_schedules = [sch for sch in workweek_schedules if sch.employee == schedule.employee]
        prev_emp_old_cost = single_employee_costs(workweek['start'], 
                                                  workweek['end'],
                                                  schedule.employee, 
                                                  prev_employee_schedules, 
                                                  departments, business_data, 
                                                  calendar_date.month, 
                                                  calendar_date.year)

        prev_employee_schedules.remove(schedule)
        prev_emp_new_cost = single_employee_costs(workweek['start'], 
                                                  workweek['end'],
                                                  schedule.employee, 
                                                  prev_employee_schedules, 
                                                  departments, business_data, 
                                                  calendar_date.month, 
                                                  calendar_date.year)
        # Calculate difference in hours and cost
        prev_emp_hours_cost_delta = calculate_cost_delta(prev_emp_old_cost, prev_emp_new_cost, 'subtract')
        
        # Add difference in cost for previous employee to overall cost/hour delta
        hours_cost_delta = calculate_cost_delta(hours_cost_delta, prev_emp_hours_cost_delta, 'add')                                       

    return hours_cost_delta
    
    
def edit_schedule_cost_change(user, schedule, new_start_dt, new_end_dt, departments, 
                              business_data, calendar_date):
    """Calculate cost differential to editing schedule with assigned employee.

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
     
    # Get the workweek that the schedule intersects with and workweek schedules
    workweek = get_start_end_of_weekday(schedule.start_datetime, user)
    workweek_schedules = (Schedule.objects.select_related('department', 'employee')
                                  .filter(user=user,
                                          end_datetime__gt=workweek['start'],
                                          start_datetime__lt=workweek['end'],
                                          employee=schedule.employee)
                                  .order_by('start_datetime', 'end_datetime')) 
    workweek_schedules = [sch for sch in workweek_schedules]

    # Get old week hours and costs                   
    old_hours_cost = single_employee_costs(workweek['start'], workweek['end'],
                                           schedule.employee, workweek_schedules, 
                                           departments, business_data, 
                                           calendar_date.month, calendar_date.year)
                                                                                                 
    # Get new week hours and costs with edited schedule
    for sch in workweek_schedules:
        if sch.id == schedule.id:
            # Do stuff:
            sch.start_datetime = new_start_dt
            sch.end_datetime = new_end_dt
            break
    new_hours_cost = single_employee_costs(workweek['start'], workweek['end'],
                                           schedule.employee, workweek_schedules, 
                                           departments, business_data, 
                                           calendar_date.month, calendar_date.year)

    # Calculate difference between old and new day hours/costs
    hours_cost_delta = calculate_cost_delta(old_hours_cost, new_hours_cost, 'subtract')
    
    return hours_cost_delta
    
    
def copy_schedules_cost_delta(user, schedules, departments, 
                              business_data, calendar_date):
    """Calculate cost differential to editing schedule with assigned employee.

    Args:
        user: django authenticated user
        schedule: The schedule that will be deleted from the database.
        
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user
        calendar_date: Datetime date containing month and year of calendar
            that the user has removed schedule from.
    Returns:
        A dictionary of departments that map to the change in cost to the 
        various departments."""
    pass
          
    
def calculate_cost_delta(old_hours_cost, new_hours_cost, operator):
    """Return difference or combiend values between old hours cost and new hours
    cost for each day, week, and month.
    
    Args:
        old_hours_cost: Hours and cost before adding/editing/removing schedules.
        new_hours_cost:  Hours and cost after adding/editing/removing schedules.
        operator: Python string indicating the kind of operation: add cost deltas
          or subtract the cost deltas.
    Returns:
        The difference between the new and old hours/costs as a hours and costs
        dictionary data structure.
    """

    # Calculate difference between old and new day hours/costs
    new_day_hours_cost = new_hours_cost['day_hours_costs']
    old_day_hours_cost = old_hours_cost['day_hours_costs']
    for date in new_day_hours_cost:
        for dep in new_day_hours_cost[date]:
            old_dep_hours = old_day_hours_cost[date][dep]['hours']
            old_dep_overtime = old_day_hours_cost[date][dep]['overtime_hours']
            old_dep_cost = old_day_hours_cost[date][dep]['cost']
            
            new_dep_hours = new_day_hours_cost[date][dep]['hours']
            new_dep_overtime = new_day_hours_cost[date][dep]['overtime_hours']
            new_dep_cost = new_day_hours_cost[date][dep]['cost']

            if operator == 'subtract':
                new_hours_cost['day_hours_costs'][date][dep]['hours'] = new_dep_hours - old_dep_hours
                new_hours_cost['day_hours_costs'][date][dep]['overtime_hours'] = new_dep_overtime - old_dep_overtime
                new_hours_cost['day_hours_costs'][date][dep]['cost'] = new_dep_cost - old_dep_cost
            else:
                new_hours_cost['day_hours_costs'][date][dep]['hours'] = new_dep_hours + old_dep_hours
                new_hours_cost['day_hours_costs'][date][dep]['overtime_hours'] = new_dep_overtime + old_dep_overtime
                new_hours_cost['day_hours_costs'][date][dep]['cost'] = new_dep_cost + old_dep_cost
            
    # Calculate difference between old and new week hours/costs
    new_week_hours_cost = new_hours_cost['workweek_hours_costs'][0]['hours_cost']
    old_week_hours_cost = old_hours_cost['workweek_hours_costs'][0]['hours_cost']
    for dep in new_week_hours_cost:
        old_dep_hours = old_week_hours_cost[dep]['hours']
        old_dep_overtime = old_week_hours_cost[dep]['overtime_hours']
        old_dep_cost = old_week_hours_cost[dep]['cost']
            
        new_dep_hours = new_week_hours_cost[dep]['hours']
        new_dep_overtime = new_week_hours_cost[dep]['overtime_hours']
        new_dep_cost = new_week_hours_cost[dep]['cost'] 
         
        if operator == 'subtract':
            new_hours_cost['workweek_hours_costs'][0]['hours_cost'][dep]['hours'] = new_dep_hours - old_dep_hours
            new_hours_cost['workweek_hours_costs'][0]['hours_cost'][dep]['overtime_hours'] = new_dep_overtime - old_dep_overtime
            new_hours_cost['workweek_hours_costs'][0]['hours_cost'][dep]['cost'] = new_dep_cost - old_dep_cost
        else:
            new_hours_cost['workweek_hours_costs'][0]['hours_cost'][dep]['hours'] = new_dep_hours + old_dep_hours
            new_hours_cost['workweek_hours_costs'][0]['hours_cost'][dep]['overtime_hours'] = new_dep_overtime + old_dep_overtime
            new_hours_cost['workweek_hours_costs'][0]['hours_cost'][dep]['cost'] = new_dep_cost + old_dep_cost
            
    # Calculate difference between old and new month costs
    new_month_cost = new_hours_cost['month_costs']
    old_month_cost = old_hours_cost['month_costs']
    for dep in new_month_cost:
        old_dep_cost = old_month_cost[dep]['cost']
        new_dep_cost = new_month_cost[dep]['cost']
        
        if operator == 'subtract':
            new_hours_cost['month_costs'][dep]['cost'] = new_dep_cost - old_dep_cost
        else:
            new_hours_cost['month_costs'][dep]['cost'] = new_dep_cost + old_dep_cost
            
    return new_hours_cost
      
    
def single_employee_costs(workweek_start, workweek_end, employee, schedules, 
                          departments, business_data, month, year):
    """Calculate costs of employee given workweek and schedules.
    
    This function returns the same data structure as all_calendar_hours_and_costs,
    but for a single employee and a single workweek.
    
    Args:
        workweek_start: Python datetime representing start of workweek.
        workweek_end: Python datetime representing end of workweek.
        employee: employee of schedules to calculate cost with.
        schedules: schedules of employee in workweek.
        departments: Queryset of all departments for user.
        business_data: Django model of business data for user.
        month: integer value of month.
        year: integer value of year.
    Returns:
        A dict containing the hours and costs of schedules, days, workweeks,
        and month for a single employee.
    """
    
    hours_and_costs = {'schedule_hours_costs': {}, 'day_hours_costs': {}, 
                       'workweek_hours_costs': [], 'month_costs': {}}
    
    single_employee_hours = employee_hours_detailed(workweek_start, workweek_end, employee, departments, 
                                             business_data, schedules, month, year)
    employee_hours = {employee: single_employee_hours}
    
    # Calculate schedule costs
    # Disabled for speed, will add if user wants specific functionality.
    #calculate_schedule_costs(employee_hours, hours_and_costs['schedule_hours_costs'], business_data)
        
    # Calculate day costs
    day_costs = calculate_day_costs(employee_hours, departments, business_data)
    hours_and_costs['day_hours_costs'].update(day_costs)
        
    # Calculate workweek costs
    workweek_costs = calculate_workweek_costs(employee_hours, departments, business_data, False)
    workweek_times = {'start': workweek_start.isoformat(), 'end': workweek_end.isoformat()}
    hours_and_costs['workweek_hours_costs'].append({'date_range': workweek_times, 'hours_cost': workweek_costs})
            
    # Calculate month costs
    workweek_costs_month = calculate_workweek_costs(employee_hours, departments, business_data, True)
    hours_and_costs['month_costs'] = workweek_costs_month
        
    return hours_and_costs