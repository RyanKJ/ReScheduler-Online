from django.test import TestCase
from django.contrib.auth.models import User
from django.test import Client
from .models import (Schedule, Department, DepartmentMembership, 
                     Employee, Vacation, RepeatUnavailability)
from .business_logic import get_availability


def create_question(question_text, days):
    """
    Creates a question with the given `question_text` and published the
    given number of `days` offset to now (negative for questions published
    in the past, positive for questions that have yet to be published).
    """
    time = timezone.now() + datetime.timedelta(days=days)
    return Question.objects.create(question_text=question_text, pub_date=time)        
                     
                     
class GetAvailabilityTest(TestCase):

    def setUp(self):
        user = User.objects.create(username='testuser')
        user.set_password('12345')
        user.save()

        c = Client()
        logged_in = c.login(username='testuser', password='12345')
        
        #Employee.objects.create(name="lion", sound="roar")
        #Department.objects.create(user=logged_in, name="TestDep")
        #DepartmentMembership.objects.create()
        
        Schedule(user=logged_in,
                 start_datetime=start_dt, end_datetime=end_dt,
                 hide_start_time=False,
                 hide_end_time=False,
                 department=dep)
    
    
    def test_no_conflicts(self):
        """Case where there are no conflicts in availability."""
        pass
        
        
    def test_schedule_conflict(self):
        """Case where there is a schedule conflict in availability."""
        pass
    
    
    def test_vacation_conflict(self):
        """Case where there is a vacation conflict in availability."""
        pass
        
        
    def test_repeate_unav_conflict(self):
        """Case where there is a repeat unavilability conflict in availability."""
        pass
        
        
    def test_overtime_conflict(self):
        """Case where there is an overtime conflict in availability."""
        pass