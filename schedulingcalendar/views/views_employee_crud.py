from django.core import serializers
from django.shortcuts import render, redirect
from django.http import (HttpResponseRedirect, HttpResponse)
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views.generic import (View, ListView, FormView, CreateView, UpdateView, 
                                  DeleteView)
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm, 
                                       SetPasswordForm)
from ..models import (Schedule, Department, DepartmentMembership, Employee, 
                     Vacation, RepeatUnavailability, DesiredTime, MonthlyRevenue,
                     Absence, BusinessData, LiveSchedule, LiveCalendar, 
                     DayNoteHeader, DayNoteBody, ScheduleSwapPetition, 
                     ScheduleSwapApplication, LiveCalendarDepartmentViewRights,
                     LiveCalendarEmployeeViewRights)    
from ..forms import (CalendarForm, AddScheduleForm, ProtoScheduleForm, 
                    VacationForm, AbsentForm, RepeatUnavailabilityForm, 
                    DesiredTimeForm, MonthlyRevenueForm, BusinessDataForm, 
                    LiveCalendarForm, LiveCalendarManagerForm, ViewLiveCalendarForm, 
                    DepartmentMembershipForm, DayNoteHeaderForm, 
                    DayNoteBodyForm, ScheduleNoteForm, ScheduleSwapPetitionForm, 
                    ScheduleSwapDecisionForm, EditScheduleForm, CopySchedulesForm,
                    EmployeeDisplaySettingsForm, SetStateLiveCalForm,
                    CalendarDisplaySettingsForm, SchedulePkForm, AddEmployeeToScheduleForm, 
                    RemoveScheduleForm)
from ..serializers import get_json_err_response
from ..custom_mixins import UserIsManagerMixin
from .views_basic_pages import manager_check
from datetime import datetime, date, time
import json



@login_required 
def employee_availability(request):
    """Display employee availabilities."""
    logged_in_user = request.user
    if request.method == 'GET':
        # Get manager corresponding to employee
        employee = (Employee.objects.select_related('user')
                                    .get(employee_user=logged_in_user))
        manager_user = employee.user
        
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
            
        return HttpResponse(template.render(context, request))
        
    else:
        msg = 'HTTP request needs to be GET. Got: ' + request.method
        return get_json_err_response(msg)
        
        
@method_decorator(login_required, name='dispatch')
class EmployeeUpdateProfileSettings(UpdateView):
    """Display employee settings and form to update these settings."""
    template_name = 'schedulingcalendar/employeeProfile.html'
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
class EmployeeListView(UserIsManagerMixin, ListView):
    """Display an alphabetical list of all employees for a managing user."""
    model = Employee
    template_name = 'schedulingcalendar/employeeList.html'
    context_object_name = 'employee_list' 
        
    def get_queryset(self):
        return (Employee.objects.filter(user=self.request.user)
                                .order_by('last_name', 'first_name'))
        
 
@method_decorator(login_required, name='dispatch') 
class EmployeeUpdateView(UserIsManagerMixin, UpdateView):
    """Display employee form and associated lists, ie vacations of employee."""
    template_name = 'schedulingcalendar/employeeInfo.html'
    fields = ['first_name', 'last_name', 'employee_id', 'email', 'phone_number',
              'wage', 'desired_hours', 'min_time_for_break',
              'break_time_in_min', 'monthly_medical', 
              'social_security']
    
    def get(self, request, **kwargs):
        self.object = Employee.objects.get(pk=self.kwargs['employee_pk'], 
                                           user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = Employee.objects.get(pk=self.kwargs['employee_pk'], 
                                   user=self.request.user)
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add departments, vacations, and other lists of employee to context."""
        now = datetime.now()
        context = super(EmployeeUpdateView, self).get_context_data(**kwargs)
        
        context['department_mem_list'] = (DepartmentMembership.objects.filter(employee=self.kwargs['employee_pk'],
                                                                              user=self.request.user)
                                                                      .order_by('priority', 'seniority'))   
        if self.object.employee_user:
            context['employee_user'] = self.object.employee_user
                                                                      
        context['future_vacation_list'] = (Vacation.objects.filter(employee=self.kwargs['employee_pk'],
                                                                   user=self.request.user,
                                                                   end_datetime__gte=now)
                                                           .order_by('start_datetime', 'end_datetime'))
                                                           
        context['past_vacation_list'] = (Vacation.objects.filter(employee=self.kwargs['employee_pk'],
                                                                 user=self.request.user,
                                                                 end_datetime__lt=now)
                                                         .order_by('start_datetime', 'end_datetime'))    
                                                         
        context['future_absence_list'] = (Absence.objects.filter(employee=self.kwargs['employee_pk'],
                                                                user=self.request.user,
                                                                end_datetime__gte=now)
                                                        .order_by('start_datetime', 'end_datetime'))
                                                           
        context['past_absence_list'] = (Absence.objects.filter(employee=self.kwargs['employee_pk'],
                                                              user=self.request.user,
                                                              end_datetime__lt=now)
                                                      .order_by('start_datetime', 'end_datetime'))                         
                                                         
        context['repeating_unavailable_list'] = (RepeatUnavailability.objects.filter(employee=self.kwargs['employee_pk'],
                                                                                     user=self.request.user)
                                                                     .order_by('weekday', 'start_time', 'end_time'))
                                                                     
        context['desired_time_list'] = (DesiredTime.objects.filter(employee=self.kwargs['employee_pk'],
                                                                  user=self.request.user)       
                                                           .order_by('weekday', 'start_time', 'end_time'))                                                                  

        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
@method_decorator(login_required, name='dispatch') 
class EmployeeCreateView(UserIsManagerMixin, CreateView):
    """Display an employee form to create a new employee."""
    template_name = 'schedulingcalendar/employeeCreate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = Employee
    fields = ['first_name', 'last_name', 'employee_id', 'email', 'phone_number',
              'wage', 'desired_hours', 'min_time_for_break',
              'break_time_in_min', 'monthly_medical', 
              'social_security']
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(EmployeeCreateView, self).form_valid(form)
        
        
@method_decorator(login_required, name='dispatch') 
class EmployeeDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete employee object."""
    template_name = 'schedulingcalendar/employeeDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = Employee
    
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def change_employee_pw_as_manager(request, **kwargs):
    """Change password of employee user account as managing user."""
    
    # TODO: Assert that employee actually belong to managing user in form_valid
    employee_pk = kwargs['employee_pk']
    employee = (Employee.objects.select_related('employee_user')
                                .get(pk=employee_pk,
                                     user=request.user))
    employee_user = employee.employee_user
    if request.method == 'POST':
        form = SetPasswordForm(employee_user, request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Your password was successfully updated!')
            return redirect(reverse('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': employee_pk}))
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = SetPasswordForm(employee_user)
        
    context = {'employee': employee, 'form': form}
    return render(request, 'schedulingcalendar/employeeUserPwUpdate.html', context)
    
    
@login_required
def change_employee_pw_as_employee(request, **kwargs):
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
    
    
@method_decorator(login_required, name='dispatch')
class EmployeeUsernameUpdateView(UserIsManagerMixin, UpdateView):
    """Display an employee user form to edit."""
    template_name = 'schedulingcalendar/employeeUsernameUpdate.html'
    model = User
    fields = ['username']
    
    
    def get(self, request, **kwargs):
        employee = (Employee.objects.select_related('employee_user')
                                    .get(pk=self.kwargs['employee_pk'],
                                         user=self.request.user))
        self.object = employee.employee_user
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        employee = (Employee.objects.select_related('employee_user')
                                    .get(pk=self.kwargs['employee_pk'],
                                         user=self.request.user))
        
        obj = employee.employee_user
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(EmployeeUsernameUpdateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
   
@method_decorator(login_required, name='dispatch')
class EmployeeUserCreateView(UserIsManagerMixin, CreateView):
    """Display employee user form to create employee user object."""
    template_name = 'schedulingcalendar/employeeUserCreate.html'
    form_class = UserCreationForm
             
    # TODO: Correct way to get a django group
    # TODO: Assert that employee actually belong to managing user in form_valid
    
    def form_valid(self, form):
        """Save employee user, add to employee profile & employee group."""
        # Save employee user object
        self.object = form.save()
        
        # Assign employee user to employee profile 1-to-1 field
        employee = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                        user=self.request.user)
        employee.employee_user = self.object
        employee.save()
        
        # Add employee user to employee group for permissions
        employee_user_group = Group.objects.get(name="Employees")
        self.object.groups.add(employee_user_group)

        return HttpResponseRedirect(self.get_success_url())
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(EmployeeUserCreateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user) 
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
        
@method_decorator(login_required, name='dispatch') 
class EmployeeUserDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete employee user object."""
    template_name = 'schedulingcalendar/employeeUserDelete.html'
    model = User

    
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(EmployeeUserDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
    
@method_decorator(login_required, name='dispatch')
class VacationUpdateView(UserIsManagerMixin, UpdateView):
    """Display vacation form to edit vacation object."""
    template_name = 'schedulingcalendar/vacationUpdate.html'
    form_class = VacationForm
    
    
    def get(self, request, **kwargs):
        self.object = Vacation.objects.get(pk=self.kwargs['vacation_pk'], 
                                           user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = Vacation.objects.get(pk=self.kwargs['vacation_pk'], 
                                   user=self.request.user)
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(VacationUpdateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
   
@method_decorator(login_required, name='dispatch')
class VacationCreateView(UserIsManagerMixin, CreateView):
    """Display vacation form to create vacation object."""
    template_name = 'schedulingcalendar/vacationCreate.html'
    form_class = VacationForm
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        employee = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                        user=self.request.user)
        form.instance.employee = employee
        return super(VacationCreateView, self).form_valid(form)
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(VacationCreateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
        
@method_decorator(login_required, name='dispatch') 
class VacationDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete vacation object."""
    template_name = 'schedulingcalendar/vacationDelete.html'
    model = Vacation
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(VacationDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
                            
                            
@method_decorator(login_required, name='dispatch')
class AbsentUpdateView(UserIsManagerMixin, UpdateView):
    """Display absent form to edit absence object."""
    template_name = 'schedulingcalendar/absenceUpdate.html'
    form_class = AbsentForm
    
    
    def get(self, request, **kwargs):
        self.object = Absence.objects.get(pk=self.kwargs['absent_pk'], 
                                           user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = Absence.objects.get(pk=self.kwargs['absent_pk'], 
                                  user=self.request.user)
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(AbsentUpdateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
   
@method_decorator(login_required, name='dispatch')
class AbsentCreateView(UserIsManagerMixin, CreateView):
    """Display absence form to create absence object."""
    template_name = 'schedulingcalendar/absenceCreate.html'
    form_class = AbsentForm
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        employee = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                        user=self.request.user)
        form.instance.employee = employee
        return super(AbsentCreateView, self).form_valid(form)
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(AbsentCreateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
        
@method_decorator(login_required, name='dispatch') 
class AbsentDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete absence object."""
    template_name = 'schedulingcalendar/absenceDelete.html'
    model = Absence
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(AbsentDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
                            
        
@method_decorator(login_required, name='dispatch')
class RepeatUnavailableUpdateView(UserIsManagerMixin, UpdateView):
    """Display repeat unavailable form to edit unav repeat object."""
    template_name = 'schedulingcalendar/repeatUnavailableUpdate.html'
    form_class = RepeatUnavailabilityForm
    
    
    def get(self, request, **kwargs):
        self.object = RepeatUnavailability.objects.get(pk=self.kwargs['repeat_unav_pk'], 
                                                       user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = RepeatUnavailability.objects.get(pk=self.kwargs['repeat_unav_pk'], 
                                               user=self.request.user)
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of unavailable repeat to context."""
        context = super(RepeatUnavailableUpdateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
   
@method_decorator(login_required, name='dispatch')
class RepeatUnavailableCreateView(UserIsManagerMixin, CreateView):
    """Display repeat unavailable form to create unav repeat object."""
    template_name = 'schedulingcalendar/repeatUnavailableCreate.html'
    form_class = RepeatUnavailabilityForm
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        employee = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                        user=self.request.user)
        form.instance.employee = employee
        return super(RepeatUnavailableCreateView, self).form_valid(form)
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of unavailable repeat to context."""
        context = super(RepeatUnavailableCreateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
@method_decorator(login_required, name='dispatch') 
class RepeatUnavailableDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete unavailable repeat object."""
    template_name = 'schedulingcalendar/repeatUnavailableDelete.html'
    model = RepeatUnavailability
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of unavailable repeat to context."""
        context = super(RepeatUnavailableDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
@method_decorator(login_required, name='dispatch')
class DesiredTimeUpdateView(UserIsManagerMixin, UpdateView):
    """Display desired time form to edit object."""
    template_name = 'schedulingcalendar/desiredTimeUpdate.html'
    form_class = DesiredTimeForm
    
    
    def get(self, request, **kwargs):
        self.object = DesiredTime.objects.get(pk=self.kwargs['desired_time_pk'], 
                                              user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = DesiredTime.objects.get(pk=self.kwargs['desired_time_pk'], 
                                      user=self.request.user)
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of desired time to context."""
        context = super(DesiredTimeUpdateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
   
@method_decorator(login_required, name='dispatch')
class DesiredTimeCreateView(UserIsManagerMixin, CreateView):
    """Display desired time form to create object."""
    template_name = 'schedulingcalendar/desiredTimeCreate.html'
    form_class = DesiredTimeForm
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        employee = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                        user=self.request.user)
        form.instance.employee = employee
        return super(DesiredTimeCreateView, self).form_valid(form)
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of desired time to context."""
        context = super(DesiredTimeCreateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
@method_decorator(login_required, name='dispatch') 
class DesiredTimeDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete desired time object."""
    template_name = 'schedulingcalendar/desiredTimeDelete.html'
    model = DesiredTime
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of desired time to context."""
        context = super(DesiredTimeDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
@method_decorator(login_required, name='dispatch')
class DepartmentMembershipUpdateView(UserIsManagerMixin, UpdateView):
    """Display department membership form to edit existing object."""
    template_name = 'schedulingcalendar/departmentMembershipUpdate.html'
    form_class = DepartmentMembershipForm
    
    def get_form_kwargs(self):
        """Set user as a value in kwargs dictionary."""
        kwargs = super(DepartmentMembershipUpdateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    
    def get(self, request, **kwargs):
        self.object = DepartmentMembership.objects.get(pk=self.kwargs['dep_mem_pk'], 
                                                       user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = DepartmentMembership.objects.get(pk=self.kwargs['dep_mem_pk'], 
                                               user=self.request.user)
        return obj
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of department membership to context."""
        context = super(DepartmentMembershipUpdateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
    
   
@method_decorator(login_required, name='dispatch')
class DepartmentMembershipCreateView(UserIsManagerMixin, CreateView):
    """Display department membership form to create object."""
    template_name = 'schedulingcalendar/departmentMembershipCreate.html'
    form_class = DepartmentMembershipForm
    
    def get_form_kwargs(self):
        """Set user as a value in kwargs dictionary."""
        kwargs = super(DepartmentMembershipCreateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        employee = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                        user=self.request.user)
        form.instance.employee = employee
        return super(DepartmentMembershipCreateView, self).form_valid(form)
        
        
    def get_context_data(self, **kwargs):
        """Add employee owner of department membership to context."""
        context = super(DepartmentMembershipCreateView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)
                                                        
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
                            
           
@method_decorator(login_required, name='dispatch') 
class DepartmentMembershipDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete department membership object."""
    template_name = 'schedulingcalendar/departmentMembershipDelete.html'
    model = DepartmentMembership
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of department membership to context."""
        context = super(DepartmentMembershipDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
    def get_success_url(self):
        """Return to employee's page after editing associated employee info."""
        return reverse_lazy('schedulingcalendar:employee_info', 
                            kwargs={'employee_pk': self.kwargs['employee_pk']})
        
        
@method_decorator(login_required, name='dispatch')
class DepartmentListView(UserIsManagerMixin, ListView):
    """Display an alphabetical list of all departments for a managing user."""
    model = Department
    template_name = 'schedulingcalendar/departmentList.html'
    context_object_name = 'department_list'
        
    def get_queryset(self):
        return Department.objects.filter(user=self.request.user).order_by('name')
        
        
    def get_context_data(self, **kwargs):
        """Add warning message to user if no departments currently exist."""
        context = super(DepartmentListView, self).get_context_data(**kwargs)
        
        departments = Department.objects.filter(user=self.request.user)
        if not departments:
            warning_msg = "You have not created any departments. Please create at least one department before creating a calendar."
            context['warning_msg'] = warning_msg
                                                        
        return context
        
        
@method_decorator(login_required, name='dispatch')
class DepartmentUpdateView(UserIsManagerMixin, UpdateView):
    """Display department form to edit existing department object."""
    template_name = 'schedulingcalendar/departmentUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:department_list')
    fields = ['name']
    
    
    def get(self, request, **kwargs):
        self.object = Department.objects.get(pk=self.kwargs['department_pk'], 
                                             user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = Department.objects.get(pk=self.kwargs['department_pk'], 
                                     user=self.request.user)
        return obj
        
   
@method_decorator(login_required, name='dispatch')
class DepartmentCreateView(UserIsManagerMixin, CreateView):
    """Display department form to create object."""
    template_name = 'schedulingcalendar/departmentCreate.html'
    success_url = reverse_lazy('schedulingcalendar:department_list')
    model = Department
    fields = ['name']
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(DepartmentCreateView, self).form_valid(form)
        
        
@method_decorator(login_required, name='dispatch') 
class DepartmentDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete department object."""
    template_name = 'schedulingcalendar/departmentDelete.html'
    success_url = reverse_lazy('schedulingcalendar:department_list')
    model = Department
    
    
@method_decorator(login_required, name='dispatch')
class MonthlyRevenueListView(UserIsManagerMixin, ListView):
    """Display an alphabetical list of all departments for a managing user."""
    model = MonthlyRevenue
    template_name = 'schedulingcalendar/monthlyRevenueList.html'
    context_object_name = 'monthly_revenue_list'
        
    def get_queryset(self):
        return (MonthlyRevenue.objects.filter(user=self.request.user)
                                      .order_by('month_year'))
        
        
@method_decorator(login_required, name='dispatch')
class MonthlyRevenueUpdateView(UserIsManagerMixin, UpdateView):
    """Display department form to edit existing department object."""
    template_name = 'schedulingcalendar/monthlyRevenueUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:monthly_revenue_list')
    form_class = MonthlyRevenueForm
    
    
    def get(self, request, **kwargs):
        self.object = MonthlyRevenue.objects.get(pk=self.kwargs['monthly_rev_pk'], 
                                                 user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = MonthlyRevenue.objects.get(pk=self.kwargs['monthly_rev_pk'], 
                                         user=self.request.user)
        return obj
        
   
@method_decorator(login_required, name='dispatch')
class MonthlyRevenueCreateView(UserIsManagerMixin, CreateView):
    """Display department form to create object."""
    template_name = 'schedulingcalendar/monthlyRevenueCreate.html'
    success_url = reverse_lazy('schedulingcalendar:monthly_revenue_list')
    form_class = MonthlyRevenueForm
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(MonthlyRevenueCreateView, self).form_valid(form)
        
        
@method_decorator(login_required, name='dispatch') 
class MonthlyRevenueDeleteView(UserIsManagerMixin, DeleteView):
    """Display a delete form to delete department object."""
    template_name = 'schedulingcalendar/monthlyRevenueDelete.html'
    success_url = reverse_lazy('schedulingcalendar:monthly_revenue_list')
    model = MonthlyRevenue
        
        
@method_decorator(login_required, name='dispatch')
class BusinessDataUpdateView(UserIsManagerMixin, UpdateView):
    """Display business data form to edit business settings."""
    template_name = 'schedulingcalendar/businessSettings.html'
    success_url = reverse_lazy('schedulingcalendar:business_update')
    form_class = BusinessDataForm
    
    
    def get(self, request, **kwargs):
        self.object = BusinessData.objects.get(user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = BusinessData.objects.get(user=self.request.user)
        return obj
        
        
@method_decorator(login_required, name='dispatch')
class CalendarDisplayUpdateView(UserIsManagerMixin, UpdateView):
    """Display calendar display settings form."""
    template_name = 'schedulingcalendar/calendarDisplaySettings.html'
    success_url = reverse_lazy('schedulingcalendar:calendar_display_settings')
    form_class = CalendarDisplaySettingsForm
    
    
    def get(self, request, **kwargs):
        self.object = BusinessData.objects.get(user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = BusinessData.objects.get(user=self.request.user)
        return obj