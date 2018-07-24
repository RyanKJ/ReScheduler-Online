from .custom_shortcuts import render_to_json_response
from django.contrib.auth.mixins import UserPassesTestMixin
from .models import Employee, BusinessData

# a mixin to add AJAX support to a form
# must be used with an object-based FormView (e.g. CreateView)
class AjaxFormResponseMixin(object):

    def form_invalid(self, form):
        return render_to_json_response(form.errors, status=400)
        

    def form_valid(self, form):
        self.object = form.save()

        # initialize an empty context
        context = {}

        # return the context as json
        return render_to_json_response(self.get_context_data(context))
        
        
class UserIsManagerMixin(UserPassesTestMixin):
    """Tests if user is manager for manager based views."""
    login_url = "/live_calendar/"
    
    def test_func(self):
        """Check if user is a manager user."""
        return self.request.user.groups.filter(name="Managers").exists()
        
        
class EmployeeCanSubmitAvailabilityApplicationMixin(UserPassesTestMixin):
    """Tests if employee's manager allows submitting availabilities."""
    login_url = "/live_calendar/"
    
    def test_func(self):
        """Check if user is a manager user."""
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=self.request.user))              
        manager_user = employee.user
        business_data = BusinessData.objects.get(user=manager_user)
        
        return business_data.right_to_submit_availability