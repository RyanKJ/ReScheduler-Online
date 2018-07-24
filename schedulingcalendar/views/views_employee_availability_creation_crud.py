from django.shortcuts import render, redirect
from django.http import (HttpResponseRedirect, HttpResponse)
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import CreateView
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm, 
                                       SetPasswordForm)
from ..models import (Employee, VacationApplication)
from ..forms import (EmployeeVacationForm)
from ..custom_mixins import EmployeeCanSubmitAvailabilityApplicationMixin



@method_decorator(login_required, name='dispatch')
class EmployeeVacationCreateView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, CreateView):
    """Display vacation form to create vacation application object."""
    template_name = 'schedulingcalendar/employeeVacationCreate.html'
    success_message = 'Vacation application was successfully created.'
    form_class = EmployeeVacationForm
              
              
    def form_valid(self, form):
        """Add employee and manager user to form for vacation creation."""
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=self.request.user))              
        form.instance.employee = employee
        form.instance.user = employee.user
        return super(EmployeeVacationCreateView, self).form_valid(form)
           
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')