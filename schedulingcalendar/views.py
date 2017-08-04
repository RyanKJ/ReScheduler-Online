from django.core import serializers
from django.shortcuts import render, redirect, get_list_or_404
from django.http import (HttpResponseRedirect, HttpResponse, 
                         HttpResponseNotFound, JsonResponse)
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.views.generic import (ListView, FormView, CreateView, UpdateView, 
                                  DeleteView)
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm, 
                                       SetPasswordForm)
from .models import (Schedule, Department, DepartmentMembership, Employee, 
                     Vacation, RepeatUnavailability, DesiredTime, MonthlyRevenue,
                     Absence, BusinessData, LiveSchedule, LiveCalendar)
from .business_logic import (get_eligables, eligable_list_to_dict,  
                             date_handler, all_calendar_costs, 
                             get_avg_monthly_revenue, add_employee_cost_change,
                             remove_schedule_cost_change, create_live_schedules)
from .forms import (CalendarForm, AddScheduleForm, VacationForm, AbsentForm,
                    RepeatUnavailabilityForm, DesiredTimeForm, 
                    MonthlyRevenueForm, BusinessDataForm, PushLiveForm,
                    LiveCalendarForm, LiveCalendarManagerForm,
                    SetActiveStateLiveCalForm, ViewLiveCalendarForm)
from custom_mixins import UserIsManagerMixin
from datetime import datetime, date, timedelta
from itertools import chain
import json


def front_page(request):
    """Display the front page for the website."""
    template = loader.get_template('schedulingcalendar/front.html')
    context = {}

    return HttpResponse(template.render(context, request))
    

def manager_check(user):
    """Checks if user is a manager user or not."""
    return user.groups.filter(name="Managers").exists()
    
 
@login_required 
def login_success(request):
    """Redirect user based on if they are manager or employee."""
    if manager_check(request.user):
        return redirect("/calendar/") # Manager page
    else:
        return redirect("/live_calendar/") 


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def calendar_page(request):
    """Display the schedule editing page for a managing user."""
    logged_in_user = request.user
    
    calendar_form = CalendarForm(logged_in_user)
    add_schedule_form = AddScheduleForm()
    view_live_form = ViewLiveCalendarForm
    template = loader.get_template('schedulingcalendar/calendar.html')
    context = {'calendar_form': calendar_form, 
               'add_sch_form': add_schedule_form,
               'view_live_form': view_live_form}

    return HttpResponse(template.render(context, request))
    
    
@login_required
def employee_calendar_page(request):
    """Display the schedule editing page for a managing user."""
    logged_in_user = request.user
    # Get manager corresponding to employee
    employee = (Employee.objects.select_related('user')
                                .get(employee_user=logged_in_user))
    manager_user = employee.user
    
    live_calendar_form = LiveCalendarForm(manager_user)
    template = loader.get_template('schedulingcalendar/employeeCalendar.html')
    context = {'live_calendar_form': live_calendar_form}

    return HttpResponse(template.render(context, request))


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def get_schedules(request):
    """Display schedules for a given user, month, year, and department."""
    logged_in_user = request.user
    if request.method == 'GET':
        form = CalendarForm(logged_in_user, request.GET)
        if form.is_valid():
            department_id = form.cleaned_data['department']
            year = form.cleaned_data['year']
            month = form.cleaned_data['month']

            # Get date month for calendar for queries
            cal_date = datetime(year, month, 1)
            lower_bound_dt = cal_date - timedelta(7)
            upper_bound_dt = cal_date + timedelta(42)
            
            # Get live_calendar to find out if calendar is active
            try:
              live_calendar = LiveCalendar.objects.get(user=logged_in_user, 
                                                       date=cal_date.date(), 
                                                       department=department_id)
              is_active = live_calendar.active
            except LiveCalendar.DoesNotExist:
              is_active = None;
            
            # Get schedule and employee models from database appropriate for calendar
            schedules = (Schedule.objects.select_related('employee')
                                         .filter(user=logged_in_user,
                                                 start_datetime__gte=lower_bound_dt,
                                                 end_datetime__lte=upper_bound_dt,
                                                 department=department_id))
            employees = set()
            for s in schedules:
                if s.employee:
                    employees.add(s.employee)
            
            # Convert schedules and employees to dicts for json dump
            schedules_as_dicts = []
            employees_as_dicts = []
            for s in schedules:
                schedule_dict = model_to_dict(s)
                schedules_as_dicts.append(schedule_dict)
            for e in employees:
                employee_dict = model_to_dict(e)
                employees_as_dicts.append(employee_dict)
                
            # Get calendar costs to display to user
            department_costs = all_calendar_costs(logged_in_user, month, year)
            avg_monthly_revenue = get_avg_monthly_revenue(logged_in_user, month)
            
            # Get business data for display settings on calendar
            business_data = (BusinessData.objects.get(user=logged_in_user))
            business_dict = model_to_dict(business_data)
              
            # Combine all appropriate data into dict for serialization
            combined_dict = {'date': cal_date.isoformat(), 
                             'department': department_id,
                             'schedules': schedules_as_dicts,
                             'employees': employees_as_dicts,
                             'department_costs': department_costs,
                             'avg_monthly_revenue': avg_monthly_revenue,
                             'display_settings': business_dict,
                             'is_active': is_active}
            combined_json = json.dumps(combined_dict, default=date_handler)
            
            return JsonResponse(combined_json, safe=False)
    
    else:
      # err_msg = "Year, Month, or Department was not selected."
      # TODO: Send back Unsuccessful Response
      pass

  
@login_required  
def get_live_schedules(request):
    """Get live schedules for given date and department."""
    logged_in_user = request.user
    if request.method == 'GET':
        # Check if browsing user is manager or employee, use appropriate form
        # depending on which kind of user called this view
        user_is_manager = manager_check(logged_in_user)
        if user_is_manager:
            employee = None
            manager_user = logged_in_user
            form = LiveCalendarManagerForm(manager_user, request.GET)
        else:
            employee = (Employee.objects.select_related('user')
                                    .get(employee_user=logged_in_user))
            manager_user = employee.user
            form = LiveCalendarForm(manager_user, request.GET)
            
        print "********************** Is form valid?: ", form.is_valid()
        print "********************** request get is: ", request.GET 
        if form.is_valid():
            department_id = form.cleaned_data['department']
            year = form.cleaned_data['year']
            month = form.cleaned_data['month']
            # LiveCalendarManagerForm form does not have employee only option,
            # so we set it to false so manager sees all schedules for calendar
            if user_is_manager:
                employee_only = False
            else:
                employee_only = form.cleaned_data['employee_only']

            # Get date month for calendar for queries
            cal_date = date(year, month, 1)
            
            try:
                live_calendar = LiveCalendar.objects.get(user=manager_user, 
                                                         date=cal_date, 
                                                         department=department_id)
                # Get schedule and employee models from database appropriate for calendar
                if employee_only:
                    live_schedules = (LiveSchedule.objects.select_related('employee')
                                                  .filter(user=manager_user,
                                                          employee=employee,
                                                          calendar=live_calendar))
                else: 
                    live_schedules = (LiveSchedule.objects.select_related('employee')
                                                  .filter(user=manager_user,
                                                          calendar=live_calendar))      
                employees = set()
                for s in live_schedules:
                    if s.employee:
                        employees.add(s.employee)
                
                # Convert live_schedules and employees to dicts for json dump
                schedules_as_dicts = []
                employees_as_dicts = []
                for s in live_schedules:
                    schedule_dict = model_to_dict(s)
                    schedules_as_dicts.append(schedule_dict)
                for e in employees:
                    employee_dict = model_to_dict(e)
                    employees_as_dicts.append(employee_dict)
                
                # Get business data for display settings on calendar
                business_data = (BusinessData.objects.get(user=manager_user))
                business_dict = model_to_dict(business_data)
                  
                # Combine all appropriate data into dict for serialization
                combined_dict = {'date': cal_date.isoformat(), 
                                 'department': department_id,
                                 'schedules': schedules_as_dicts,
                                 'employees': employees_as_dicts,
                                 'version': live_calendar.version,
                                 'display_settings': business_dict}
                combined_json = json.dumps(combined_dict, default=date_handler)
                
                return JsonResponse(combined_json, safe=False)
                
            except LiveCalendar.DoesNotExist:
                department_name = Department.objects.get(pk=department_id).name
                message = "No Schedules For " + department_name + " Calendar: " + cal_date.strftime("%B, %Y")
                response = HttpResponseNotFound(message)
                return response
    
    else:
      # err_msg = "Year, Month, or Department was not selected."
      # TODO: Send back Unsuccessful Response
      pass  
      
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def add_schedule(request):
    """Add schedule to the database and return string of added schedule."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = AddScheduleForm(request.POST)
        if form.is_valid():
            department = form.cleaned_data['department']
            date = form.cleaned_data['add_date']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            hide_start = form.cleaned_data['hide_start']
            hide_end = form.cleaned_data['hide_end']
            
            start_dt = datetime.combine(date, start_time)
            end_dt = datetime.combine(date, end_time)
            
            # TODO: Assert department belongs to user after form cleaning?
            dep = Department.objects.get(user=logged_in_user, pk=department)
            schedule = Schedule(user=logged_in_user,
                                start_datetime=start_dt, end_datetime=end_dt,
                                hide_start_time=hide_start,
                                hide_end_time=hide_end,
                                department=dep)
            schedule.save()
            schedule_dict = model_to_dict(schedule)
            schedule_json = json.dumps(schedule_dict, default=date_handler)
            
            return JsonResponse(schedule_json, safe=False)
            
    else:
        # TODO: Case where invalid HTTP Request handling
        pass
        
     
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")    
def get_schedule_info(request):
    """Returns information for schedule such as eligable employees."""
    logged_in_user = request.user

    schedule_pk = request.GET['pk']
    schedule = (Schedule.objects.select_related('department', 'employee', 'user')
                                .get(user=logged_in_user, pk=schedule_pk))
    
    eligable_list = get_eligables(schedule)
    eligable_dict_list = eligable_list_to_dict(eligable_list)
    json_data = json.dumps(eligable_dict_list, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    

@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def add_employee_to_schedule(request):
    """Assign employee to schedule."""
    logged_in_user = request.user
    schedule_pk = request.POST['schedule_pk']
    employee_pk = request.POST['employee_pk']
    cal_date = datetime.strptime(request.POST['cal_date'], "%Y-%m-%d")
    # Get schedule and its cost with old employee
    schedule = (Schedule.objects.select_related('department', 'employee')
                                .get(user=logged_in_user, pk=schedule_pk))
    new_employee = Employee.objects.get(user=logged_in_user, pk=employee_pk)
    
    # Get cost of assigning new employee to schedule
    departments = Department.objects.filter(user=logged_in_user)
    business_data = BusinessData.objects.get(user=logged_in_user)
    cost_delta = add_employee_cost_change(logged_in_user, schedule, new_employee,
                                          departments, business_data, cal_date)
    
    # Assign new employee to schedule
    schedule.employee = new_employee
    schedule.save(update_fields=['employee'])
    
    # Process information for json dump
    schedule_dict = model_to_dict(schedule)
    employee_dict = model_to_dict(new_employee)
    data = {'schedule': schedule_dict, 'employee': employee_dict, 
            'cost_delta': cost_delta}
    json_data = json.dumps(data, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    

@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def remove_schedule(request):
    """Remove schedule from the database."""
    logged_in_user = request.user
    schedule_pk = request.POST['schedule_pk']
    cal_date = datetime.strptime(request.POST['cal_date'], "%Y-%m-%d")
    schedule = (Schedule.objects.select_related('department', 'employee')
                                .get(user=logged_in_user, pk=schedule_pk))
                                
    cost_delta = {}
    if schedule.employee: # Get change of cost if employee was assigned
      departments = Department.objects.filter(user=logged_in_user)
      business_data = BusinessData.objects.get(user=logged_in_user)
      cost_delta = remove_schedule_cost_change(logged_in_user, schedule,
                                               departments, business_data,
                                               cal_date)
      
    schedule.delete()
    json_info = json.dumps({'schedule_pk': schedule_pk, 'cost_delta': cost_delta},
                            default=date_handler)
                            
    return JsonResponse(json_info, safe=False)
    
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def push_live(request):
    """Create a live version of schedules for employee users to query."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = PushLiveForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            department_pk = form.cleaned_data['department']
            department = Department.objects.get(pk=department_pk)
            live_calendar, created = LiveCalendar.objects.get_or_create(user=logged_in_user, 
                                                                        date=date, 
                                                                        department=department)                                  
            if created:
                create_live_schedules(logged_in_user, live_calendar)
            else:
                old_live_schedules = LiveSchedule.objects.filter(user=logged_in_user,
                                                                 calendar=live_calendar)
                old_live_schedules.delete()
                create_live_schedules(logged_in_user, live_calendar)
                live_calendar.active = True
                live_calendar.version += 1
                live_calendar.save()
                
            json_info = json.dumps({'message': 'Successfully pushed calendar live.'})
            return JsonResponse(json_info, safe=False)
        
        json_info = json.dumps({'message': 'Failed to push calendar live.'})
        return JsonResponse(json_info, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests
        
        
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def set_active_state(request):
    """Deactivate the live_calendar for given month"""
    logged_in_user = request.user
    if request.method == 'POST':
        form = SetActiveStateLiveCalForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            department_id = form.cleaned_data['department']
            new_active_state = form.cleaned_data['active']
            try: # Get live_calendar to find out if calendar is active
              live_calendar = LiveCalendar.objects.get(user=logged_in_user, 
                                                       date=date, 
                                                       department=department_id)
              live_calendar.active = new_active_state
              live_calendar.save()
              # Return success message
              if new_active_state:
                  message = 'Successfully reactivated the live calendar.'
                  active_state = True
              else:
                  message = 'Successfully deactivated the live calendar.'
                  active_state = False
            except LiveCalendar.DoesNotExist:
                message = 'No live calendar currently exists for this month, year, and department.'
                active_state = None
                
            json_info = json.dumps({'message': message, 'is_active': active_state})
            return JsonResponse(json_info, safe=False)
            
        json_info = json.dumps({'message': 'Invalid data used to set active state of live calendar.'})
        return JsonResponse(json_info, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests      
        
   
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def view_live_schedules(request):   
    """Redirect manager to view corresponding live_calendar."""
    logged_in_user = request.user
    if request.method == 'GET':
        form = ViewLiveCalendarForm(request.GET)
        print "request get is: ", request.GET
        if form.is_valid():
            date = form.cleaned_data['date']
            print "************* date for view live is: ", date
            print "request get is: ", request.GET
            department_id = form.cleaned_data['department']
            try: # Get live_calendar to find out if calendar is active
                live_calendar = LiveCalendar.objects.get(user=logged_in_user, 
                                                         date=date, 
                                                         department=department_id)
                is_active = live_calendar.active
                if is_active:
                    template = loader.get_template('schedulingcalendar/managerCalendar.html')
                    live_calendar_form = LiveCalendarManagerForm(logged_in_user)
                    department = Department.objects.get(pk=department_id)
                    context = {'live_calendar_form': live_calendar_form,
                               'date': date,
                               'department': department_id,
                               'department_name': department.name}
                    return HttpResponse(template.render(context, request))
                else:
                    message = 'Successfully deactivated the live calendar.'
            except:
                message = 'No live calendar currently exists for this month, year, and department.'
                
            json_info = json.dumps({'message': message})
            return JsonResponse(json_info, safe=False)      
               
        json_info = json.dumps({'message': 'Invalid data used to view live calendar.'})
        return JsonResponse(json_info, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests     
                   
                  
@method_decorator(login_required, name='dispatch')
class EmployeeListView(UserIsManagerMixin, ListView):
    """Display an alphabetical list of all employees for a managing user."""
    model = Employee
    template_name = 'schedulingcalendar/employeeList.html'
    context_object_name = 'employee_list' 
        
    def get_queryset(self):
        return (Employee.objects.filter(user=self.request.user)
                                .order_by('first_name', 'last_name'))
        
 
@method_decorator(login_required, name='dispatch') 
class EmployeeUpdateView(UserIsManagerMixin, UpdateView):
    """Display employee form and associated lists, ie vacations of employee."""
    template_name = 'schedulingcalendar/employeeInfo.html'
    fields = ['first_name', 'last_name', 'employee_id', 'email',
              'wage', 'desired_hours', 'monthly_medical',
              'workmans_comp', 'social_security']
    
    def get(self, request, **kwargs):
        self.object = Employee.objects.get(pk=self.kwargs['employee_pk'], 
                                           user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        print "************** object in get request method is: ", self.object
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
    fields = ['first_name', 'last_name', 'employee_id', 'email',
              'wage', 'desired_hours', 'monthly_medical',
              'workmans_comp', 'social_security']
              
              
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
    fields = ['department', 'priority', 'seniority']
    
    
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
    model = DepartmentMembership
    fields = ['department', 'priority', 'seniority']
              
              
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
        

        
    