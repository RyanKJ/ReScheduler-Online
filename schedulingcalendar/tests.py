from django.test import TestCase
from django.contrib.auth.models import User
from django.test import Client
from .models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime, LiveSchedule, LiveCalendar)
from .business_logic import get_availability
from datetime import datetime, date, timedelta


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
                     
                     
class GetAvailabilityTest(TestCase):

    def setUp(self):
        """Create users, departments, employee and schedule objects necessary
        to execute the get_availability function.
        """
        user = User.objects.create(username='testuser')
        user.set_password('12345')
        user.save()
        
        # Create employee, a 1-hour schedule, then assign employee to schedule
        business_data = create_business_data(user)
        department = create_department(user)                     
        employee = create_employee(user)
        start_dt = datetime(2017, 1, 1, 0, 0, 0)
        end_dt = datetime(2017, 1, 1, 1, 0, 0)
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
        self.assertEqual(availability['Hours Scheduled'], 2)
        self.assertEqual(availability['(O)'], False)
        
        
    def test_schedule_conflict(self):
        """Case where there is a schedule conflict in availability."""
        user = User.objects.first()
        employee = Employee.objects.first()
        department = Department.objects.first()
        schedule_conflict = Schedule.objects.first()
        
        # Make an overlapping schedule to assign employee to:
        start_dt = datetime(2017, 1, 1, 0, 59, 59)
        end_dt = datetime(2017, 1, 1, 1, 0, 1)
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
        pass
        
        
    def test_repeate_unav_conflict(self):
        """Case where there is a repeat unavilability conflict in availability."""
        pass
        
        
    def test_overtime_conflict(self):
        """Case where there is an overtime conflict in availability."""
        pass