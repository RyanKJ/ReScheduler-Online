from django.shortcuts import render, redirect
from django.http import (HttpResponseRedirect, HttpResponse, HttpResponseNotFound,
Http404)
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm,
                                       SetPasswordForm)
from ..models import (Employee, VacationApplication, BusinessData,
                      DepartmentMembership, Vacation, Absence,
                      RepeatUnavailability, DesiredTime)
from ..forms import (EmployeeVacationForm, EmployeeDisplaySettingsForm)
from ..custom_mixins import EmployeeCanSubmitAvailabilityApplicationMixin
from datetime import datetime


@login_required
def employee_availability(request):
    """Display employee availabilities."""
    logged_in_user = request.user
    if request.method == 'GET':
        # Get manager corresponding to employee
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=logged_in_user))
        manager_user = employee.user
        business_data = BusinessData.objects.get(user=manager_user)

        template = loader.get_template('schedulingcalendar/employeeAvailability.html')
        context = {}

        # Get availability information for employee
        now = datetime.now()
        context['desired_hours'] = employee.desired_hours

        context['department_mem_list'] = (DepartmentMembership.objects.filter(employee=employee,
                                                                              user=manager_user)
                                                                      .order_by('priority', 'seniority'))

        context['future_vacation_list'] = (Vacation.objects.filter(employee=employee,
                                                                   user=manager_user,
                                                                   end_datetime__gte=now)
                                                           .order_by('start_datetime', 'end_datetime'))

        context['past_vacation_list'] = (Vacation.objects.filter(employee=employee,
                                                                 user=manager_user,
                                                                 end_datetime__lt=now)
                                                         .order_by('start_datetime', 'end_datetime'))

        context['future_absence_list'] = (Absence.objects.filter(employee=employee,
                                                                user=manager_user,
                                                                end_datetime__gte=now)
                                                        .order_by('start_datetime', 'end_datetime'))

        context['past_absence_list'] = (Absence.objects.filter(employee=employee,
                                                               user=manager_user,
                                                               end_datetime__lt=now)
                                                       .order_by('start_datetime', 'end_datetime'))

        context['repeating_unavailable_list'] = (RepeatUnavailability.objects.filter(employee=employee,
                                                                                     user=manager_user)
                                                                     .order_by('weekday', 'start_time', 'end_time'))

        context['desired_time_list'] = (DesiredTime.objects.filter(employee=employee,
                                                                   user=manager_user))

        context['availability_create_right'] = business_data.right_to_submit_availability

        if business_data.right_to_submit_availability:
            context['vacation_application_list'] = (VacationApplication.objects.filter(employee=employee,
                                                                                   user=manager_user)
                                                                               .order_by('start_datetime', 'end_datetime'))

        return HttpResponse(template.render(context, request))

    else:
        msg = 'HTTP request needs to be GET. Got: ' + request.method
        return get_json_err_response(msg)


@method_decorator(login_required, name='dispatch')
class EmployeeUpdateProfileSettings(SuccessMessageMixin, UpdateView):
    """Display employee settings and form to update these settings."""
    template_name = 'schedulingcalendar/employeeProfile.html'
    success_message = 'Schedule display settings successfully updated'
    form_class = EmployeeDisplaySettingsForm
    success_url = reverse_lazy('schedulingcalendar:employee_profile_settings')


    def get(self, request, **kwargs):
        self.object = Employee.objects.get(employee_user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)


    def get_object(self, queryset=None):
        obj = Employee.objects.get(employee_user=self.request.user)
        return obj


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


@method_decorator(login_required, name='dispatch')
class EmployeeVacationApplicationDeleteView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, DeleteView):
    """Display a delete form to delete vacation object."""
    template_name = 'schedulingcalendar/employeeVacationDelete.html'
    success_message = 'Vacation successfully deleted'
    model = VacationApplication


    def delete(self, request, *args, **kwargs):
        """Delete obj if user is owner of obj."""
        self.object = self.get_object()
        if employee_is_obj_owner_test(request.user, self.object):
            success_url = self.get_success_url()
            self.object.delete()
            return HttpResponseRedirect(success_url)
        else:
            return HttpResponseNotFound('<h1>Vacation application not found</h1>')


    def get_success_url(self):
        """Return to employee's availability page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')


def employee_is_obj_owner_test(user, obj):
    """Checks that the request user is the owner of the object they are requesting."""
    return user.id == obj.employee.employee_user.id
