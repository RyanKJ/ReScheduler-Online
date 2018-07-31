from django.shortcuts import render, redirect
from django.http import (HttpResponseRedirect, HttpResponse, HttpResponseNotFound,
Http404)
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm,
                                       SetPasswordForm)
from ..models import (Employee, BusinessData, DepartmentMembership, Vacation,
                      Absence, RepeatUnavailability, DesiredTime, VacationApplication,
                      AbsenceApplication, RepeatUnavailabilityApplication)
from ..forms import (EmployeeVacationForm, EmployeeDisplaySettingsForm,
                     EmployeeAbsentForm, EmployeeRepeatUnavailabilityForm,
                     DesiredTimeForm)
from ..custom_mixins import EmployeeCanSubmitAvailabilityApplicationMixin
from datetime import datetime, timedelta



@login_required
def change_employee_pw_as_employee(request, SuccessMessageMixin, **kwargs):
    """Change password of employee user account as employee user."""
    if request.method == 'POST':
        employee = (Employee.objects.select_related('employee_user')
                                    .get(pk=self.kwargs['employee_pk'],
                                         user=self.request.user))
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('accounts:change_password')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {
        'form': form
    })
    

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
            seven_days_ago = timezone.now() - timedelta(7)
            context['vacation_application_list'] = (VacationApplication.objects.filter(employee=employee, user=manager_user, datetime_of_approval__gte=seven_days_ago)
                                                                               .order_by('start_datetime', 'end_datetime'))
            context['absence_application_list'] = (AbsenceApplication.objects.filter(employee=employee, user=manager_user, datetime_of_approval__gte=seven_days_ago)
                                                                             .order_by('start_datetime', 'end_datetime'))  
            context['repeat_unavailability_application_list'] = (RepeatUnavailabilityApplication.objects.filter(employee=employee, user=manager_user, datetime_of_approval__gte=seven_days_ago)
                                                                                                        .order_by('weekday', 'start_time', 'end_time'))
                                                                               

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
class EmployeeVacationApplicationCreateView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, CreateView):
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
        return super(EmployeeVacationApplicationCreateView, self).form_valid(form)


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
        
        
@method_decorator(login_required, name='dispatch')
class EmployeeAbsenceApplicationCreateView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, CreateView):
    """Display absence form to create vacation application object."""
    template_name = 'schedulingcalendar/employeeAbsenceCreate.html'
    success_message = 'Unavailability application was successfully created.'
    form_class = EmployeeAbsentForm


    def form_valid(self, form):
        """Add employee and manager user to form for absence creation."""
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=self.request.user))
        form.instance.employee = employee
        form.instance.user = employee.user
        return super(EmployeeAbsenceApplicationCreateView, self).form_valid(form)


    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')
        
        
@method_decorator(login_required, name='dispatch')
class EmployeeAbsenceApplicationDeleteView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, DeleteView):
    """Display a delete form to delete vacation object."""
    template_name = 'schedulingcalendar/employeeAbsenceDelete.html'
    success_message = 'Absence successfully deleted'
    model = AbsenceApplication


    def delete(self, request, *args, **kwargs):
        """Delete obj if user is owner of obj."""
        self.object = self.get_object()
        if employee_is_obj_owner_test(request.user, self.object):
            success_url = self.get_success_url()
            self.object.delete()
            return HttpResponseRedirect(success_url)
        else:
            return HttpResponseNotFound('<h1>Absence application not found</h1>')


    def get_success_url(self):
        """Return to employee's availability page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')
        
        
@method_decorator(login_required, name='dispatch')
class EmployeeRepeatUnavailabilityApplicationCreateView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, CreateView):
    """Displayrepeat unavailability form to create vacation application object."""
    template_name = 'schedulingcalendar/employeeRepeatUnavailableCreate.html'
    success_message = 'Repeat unavailability application was successfully created.'
    form_class = EmployeeRepeatUnavailabilityForm


    def form_valid(self, form):
        """Add employee and manager user to form for repeating unavailability creation."""
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=self.request.user))
        form.instance.employee = employee
        form.instance.user = employee.user
        return super(EmployeeRepeatUnavailabilityApplicationCreateView, self).form_valid(form)


    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')
        
        
@method_decorator(login_required, name='dispatch')
class EmployeeRepeatUnavailabilityApplicationDeleteView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, DeleteView):
    """Display a delete form to delete vacation object."""
    template_name = 'schedulingcalendar/employeeRepeatUnavailableDelete.html'
    success_message = 'Repeating unavailability successfully deleted'
    model = RepeatUnavailabilityApplication


    def delete(self, request, *args, **kwargs):
        """Delete obj if user is owner of obj."""
        self.object = self.get_object()
        if employee_is_obj_owner_test(request.user, self.object):
            success_url = self.get_success_url()
            self.object.delete()
            return HttpResponseRedirect(success_url)
        else:
            return HttpResponseNotFound('<h1>Repeat Unavailability application not found</h1>')


    def get_success_url(self):
        """Return to employee's availability page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')
        
        
@method_decorator(login_required, name='dispatch')
class EmployeeDesiredTimeCreateView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, CreateView):
    """Display desired time form to create object."""
    template_name = 'schedulingcalendar/employeeDesiredTimeCreate.html'
    success_message = 'Desired time successfully created'
    form_class = DesiredTimeForm


    def form_valid(self, form):
        """Add employee and manager user to form for desired time creation."""
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=self.request.user))
        form.instance.employee = employee
        form.instance.user = employee.user
        return super(EmployeeDesiredTimeCreateView, self).form_valid(form)



    def get_success_url(self):
        """Return to employee's availability page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')


@method_decorator(login_required, name='dispatch')
class EmployeeDesiredTimeDeleteView(EmployeeCanSubmitAvailabilityApplicationMixin, SuccessMessageMixin, DeleteView):
    """Display a delete form to delete desired time object."""
    template_name = 'schedulingcalendar/employeeDesiredTimeDelete.html'
    success_message = 'Desired time successfully deleted'
    model = DesiredTime


    def delete(self, request, *args, **kwargs):
        """Delete obj if user is owner of obj."""
        self.object = self.get_object()
        if employee_is_obj_owner_test(request.user, self.object):
            success_url = self.get_success_url()
            self.object.delete()
            return HttpResponseRedirect(success_url)
        else:
            return HttpResponseNotFound('<h1>Desired time not found</h1>')


    def get_success_url(self):
        """Return to employee's availability page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_availability')
        

def employee_is_obj_owner_test(user, obj):
    """Checks that the request user is the owner of the object they are requesting."""
    return user.id == obj.employee.employee_user.id
