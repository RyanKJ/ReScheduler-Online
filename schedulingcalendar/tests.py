from django.test import TestCase
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from .models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime, LiveSchedule, LiveCalendar)
from .business_logic import get_availability, get_eligibles
from datetime import datetime, date, time, timedelta
import pytz
import math


def create_tzaware_datetime(datetime):
    """Make datetime aware of server timezone."""
    time_zone = timezone.get_default_timezone_name()
    aware_dt = pytz.timezone(time_zone).localize(datetime)
    
    return aware_dt


def create_employee(user, first_name='A', last_name='1', email="a@a.com", 
                    employee_id=1, wage=1, desired_hours=40, monthly_medical=0,
                    workmans_comp=7.5, social_security=7.5):
    """Creates an employee given a user, with the option to customize employee."""
    employee = Employee.objects.create(user=user, first_name=first_name, last_name=last_name, 
                                       email=email, employee_id=employee_id, wage=wage, 
                                       desired_hours=desired_hours, monthly_medical=monthly_medical,
                                       workmans_comp=workmans_comp, social_security=social_security)
    return employee
    
    
def create_department(user, name='TestDep'):
    """Creates a department with optional customization of name."""
    return Department.objects.create(user=user, name=name)
    
    
def create_business_data(user):
    """Creates a business data object for user."""
    return BusinessData.objects.create(user=user)
    
    
def create_schedule(user, start_dt, end_dt, department, hide_start_time=False, 
                    hide_end_time=False, employee=None):
    """Creates a schedule with optional customization."""
    schedule = Schedule.objects.create(user=user, start_datetime=start_dt, 
                                       end_datetime=end_dt, hide_start_time=hide_start_time, 
                                       hide_end_time=hide_end_time,
                                       department=department, employee=employee)      

    return schedule
    
    
def create_vacation(user, employee, start_dt, end_dt):
    """Creates a vacation with optional customization."""
    vacation = Vacation.objects.create(user=user, start_datetime=start_dt, 
                                       end_datetime=end_dt, employee=employee)      

    return vacation
 

def create_absence(user, employee, start_dt, end_dt):
    """Creates an absence with optional customization."""
    absence = Absence.objects.create(user=user, start_datetime=start_dt, 
                                       end_datetime=end_dt, employee=employee)      

    return absence
 
    
def create_unav_repeat(user, employee, start, end, weekday):
    """Creates a repeating unavailability with optional customization."""
    unav_repeat = RepeatUnavailability.objects.create(user=user, start_time=start, 
                                                      end_time=end, weekday=weekday,
                                                      employee=employee)      

    return unav_repeat
    
    
def create_desired_time(user, employee, start, end, weekday):
    """Creates a repeating desired time with optional customization."""
    desired_time = DesiredTime.objects.create(user=user, start_time=start, 
                                              end_time=end, weekday=weekday,
                                              employee=employee)      

    return desired_time
    
    
def create_dep_membership(user, employee, department, dep_priority, dep_seniority):
    """Creates a repeating desired time with optional customization."""
    dep_mem = DepartmentMembership.objects.create(user=user, employee=employee,
                                                  department=department,
                                                  priority=dep_priority, 
                                                  seniority=dep_seniority)    
                                                  
    return
    
    
def create_many_conflicts(employees, department, availability_properties, user):
    """Create employees with conflicts to test get_eligable method."""
    if employees == [] or availability_properties == []:
        return
        
    half =  int(math.floor(len(employees) / 2))
    lower_half_emp = employees[0:half]
    upper_half_emp = employees[half:]
    
    print
    print
    print "lower half is: ", lower_half_emp
    print
    print
    print "upper half is: ", upper_half_emp
    
    avail_prop = availability_properties.pop(0)
    for employee in lower_half_emp:
        _create_availability_property(employee, department, avail_prop, 'lower', user)
    for employee in upper_half_emp:
        _create_availability_property(employee, department, avail_prop, 'upper', user)
        
    create_many_conflicts(lower_half_emp, department, availability_properties, user)
    create_many_conflicts(upper_half_emp, department, availability_properties, user)
    
 
def _create_availability_property(employee, department, avail_property, list_side, user):
    """Create the corresponding conflict for employee given property."""
    if list_side == 'lower':
        if avail_property == 'Dep Priority':
            create_dep_membership(user, employee, department, 0, 0)
        elif avail_property == 'Desired Times':
            start = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
            end = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
            weekday = 0
            desired_time = create_desired_time(user, start=start, end=end, 
                                               weekday=weekday, employee=employee)
        elif avail_property == 'Desired Hours':
            return    
    else:
        if avail_property == 'Dep Priority':
            create_dep_membership(user, employee, department, 1, 1)
        elif avail_property == 'Desired Times':
            return
        elif avail_property == 'Desired Hours':
            employee.desired_hours = -10000
            employee.save()
        elif avail_property == '(O)':
            for i in range(3, 8):    
                start_dt = create_tzaware_datetime(datetime(2017, 1, i, 0, 0, 0))
                end_dt = create_tzaware_datetime(datetime(2017, 1, i, 10, 0, 0))
                t_delta = end_dt - start_dt
                schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                           department=department, employee=employee)   
        elif avail_property == '(U)':
            start = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
            end = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
            weekday = 0
            unav_repeat = create_unav_repeat(user, start=start, end=end, 
                                             weekday=weekday, employee=employee)
        elif avail_property == '(A)':
            start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
            end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
            absence = create_absence(user, start_dt=start_dt, end_dt=end_dt,
                                     employee=employee)
        elif avail_property == '(V)':
            start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
            end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
            vacation = create_vacation(user, start_dt=start_dt, end_dt=end_dt,
                                       employee=employee)
        elif avail_property == '(S)':
            start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
            end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
            schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                       department=department, employee=employee)
            
                     
class GetAvailabilityTest(TestCase):
    """Test class for the get_availability function.

    The get_availability function returns a dictionary of string keys that map
    to querysets of conflicts, a boolean indicating if employee is in overtime, 
    and a floating number of how many hours the employee will be working if 
    assigned to the schedule supplied as an argument in the get_availability
    function.
    
    These tests test each of these dictionary key values outputted by get_availability.
    """

    def setUp(self):
        """
        Create users, departments, employee and schedule objects necessary
        to execute the get_availability function.
        """
        
        user = User.objects.create(username='testuser')
        user.set_password('12345')
        user.save()
        
        # Create employee, a 1-hour schedule, then assign employee to schedule
        business_data = create_business_data(user)
        department = create_department(user)                     
        employee = create_employee(user)
        start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 0, 0))
        end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 0))
        schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                   department=department, employee=employee)
                                   
    
    def test_no_conflicts(self):
        """Case where there are no conflicts in availability."""          
        employee = Employee.objects.first()
        schedule = Schedule.objects.first()
        availability = get_availability(employee, schedule)
        
        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 1)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_schedule_conflict(self):
        """Case where there is a schedule conflict in availability."""
        user = User.objects.first()
        employee = Employee.objects.first()
        department = Department.objects.first()
        schedule_conflict = Schedule.objects.first()
        
        # Make an overlapping schedule to assign employee to:
        start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
        end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
        schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                   department=department, employee=employee)
        availability = get_availability(employee, schedule)          

        self.assertEqual(list(availability['(S)']), [schedule_conflict])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 1)
        self.assertEqual(availability['(O)'], False)
    
    
    def test_vacation_conflict(self):
        """Case where there is a vacation conflict in availability."""
        user = User.objects.first()
        employee = Employee.objects.first()
        schedule_conflict = Schedule.objects.first()
        
        # Make an overlapping schedule to assign employee to:
        start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
        end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
        vacation = create_vacation(user, start_dt=start_dt, end_dt=end_dt,
                                   employee=employee)
        availability = get_availability(employee, schedule_conflict)          

        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [vacation])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 1)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_absence_conflict(self):
        """Case where there is an absence conflict in availability."""
        user = User.objects.first()
        employee = Employee.objects.first()
        schedule_conflict = Schedule.objects.first()
        
        # Make an overlapping schedule to assign employee to:
        start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
        end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
        absence = create_absence(user, start_dt=start_dt, end_dt=end_dt,
                                   employee=employee)
        availability = get_availability(employee, schedule_conflict)          

        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [absence])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 1)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_repeate_unav_conflict(self):
        """Case where there is a repeat unavilability conflict in availability."""
        user = User.objects.first()
        employee = Employee.objects.first()
        department = Department.objects.first()
        schedule_conflict = Schedule.objects.first()
        
        # Make an overlapping schedule to assign employee to:
        start = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
        end = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
        weekday = 0
        unav_repeat = create_unav_repeat(user, start=start, end=end, 
                                         weekday=weekday, employee=employee)
        availability = get_availability(employee, schedule_conflict)      
 
        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [unav_repeat])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 1)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_desired_time_overlap(self):
        """Case where employee's desired time overlaps with schedule."""
        user = User.objects.first()
        employee = Employee.objects.first()
        department = Department.objects.first()
        schedule_conflict = Schedule.objects.first()
        
        # Make an overlapping schedule to assign employee to:
        start = create_tzaware_datetime(datetime(2017, 1, 2, 0, 59, 59))
        end = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 1))
        weekday = 0
        desired_time = create_desired_time(user, start=start, end=end, 
                                          weekday=weekday, employee=employee)
        availability = get_availability(employee, schedule_conflict)      
 
        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [desired_time])
        self.assertEqual(availability['Hours Scheduled'], 1)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_hours_schedule(self):
        """Test that get_availability outputs correct # hours assigned."""
        user = User.objects.first()
        employee = Employee.objects.first()
        department = Department.objects.first()
        schedule_conflict = Schedule.objects.first()
        # Create four eight-hour schedules for week to put employee in overtime                    
        for i in range(3, 7):    
            start_dt = create_tzaware_datetime(datetime(2017, 1, i, 0, 0, 0))
            end_dt = create_tzaware_datetime(datetime(2017, 1, i, 8, 0, 0))
            t_delta = end_dt - start_dt
            schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                       department=department, employee=employee)
                                   
        availability = get_availability(employee, schedule_conflict)
        
        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 33)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_overtime_conflict(self):
        """Case where there is an overtime conflict in availability."""
        user = User.objects.first()
        employee = Employee.objects.first()
        department = Department.objects.first()
        schedule_conflict = Schedule.objects.first()
        # Create five ten-hour schedules for week to put employee in overtime                    
        for i in range(3, 8):    
            start_dt = create_tzaware_datetime(datetime(2017, 1, i, 0, 0, 0))
            end_dt = create_tzaware_datetime(datetime(2017, 1, i, 10, 0, 0))
            t_delta = end_dt - start_dt
            schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                       department=department, employee=employee)
                                   
        availability = get_availability(employee, schedule_conflict)
        
        self.assertEqual(list(availability['(S)']), [])
        self.assertEqual(list(availability['(V)']), [])
        self.assertEqual(list(availability['(A)']), [])
        self.assertEqual(list(availability['(U)']), [])
        self.assertEqual(list(availability['Desired Times']), [])
        self.assertEqual(availability['Hours Scheduled'], 51)
        self.assertEqual(availability['(O)'], True)
        

class GetEligiblesTest(TestCase):
    """
    get_eligibles is a sorting method using the heuristic of 'availability', 
    sorting all eligable employees and returning this sorted list. We test the 
    method by returning a sorted list of employees that is large enough such 
    that every flag that can affect eligiblity is tested. For example, all
    combinations of schedule conflicts, vacations, overtime, etc. are
    calculated and tested to make sure employees are ranked accordingly.
    """
    
    def setUp(self):
        """
        Create users, departments, employee and schedule objects necessary
        to execute the get_eligible function.
        """
        
        user = User.objects.create(username='testuser')
        user.set_password('12345')
        user.save()
        
        # Create employee, a 1-hour schedule, then assign employee to schedule
        business_data = create_business_data(user)
        department_1 = create_department(user, "A")
        department_2 = create_department(user, "B")
        
        employees = []
        avail_prop = ['(S)', '(V)', '(A)', '(U)', '(O)', 'Dep Priority', 
                      'Desired Times', 'Desired Hours']
                                    
        for i in range(1, 257):
            employee = create_employee(user, first_name=str(i), last_name=str(i))
            employees.append(employee)

        create_many_conflicts(employees, department_1, avail_prop, user)

        
    def test_get_eligibles(self):
        user = User.objects.get(username='testuser')
        department_1 = Department.objects.get(user=user, name="A")
        start_dt = create_tzaware_datetime(datetime(2017, 1, 2, 0, 0, 0))
        end_dt = create_tzaware_datetime(datetime(2017, 1, 2, 1, 0, 0))
        schedule = create_schedule(user, start_dt=start_dt, end_dt=end_dt,
                                   department=department_1, employee=None)
        eligible_return_value = get_eligibles(schedule)
        eligibles = eligible_return_value['eligables']
        
        
        print "eligible count is: ", len(eligibles)
        print "eligibles are: "
        
        for i in range(1, len(eligibles)): 
            print eligibles[i]
        
        #for i in range(1, 257):
        #    employee = create_employee(user, first_name=str(i), last_name=str(i))
        #    employees.append(employee)
        
        

