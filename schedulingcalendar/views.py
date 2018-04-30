from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_list_or_404
from django.http import (HttpResponseRedirect, HttpResponse, 
                         HttpResponseNotFound, JsonResponse)
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib import messages
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.views.generic import (ListView, FormView, CreateView, UpdateView, 
                                  DeleteView)
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm, 
                                       SetPasswordForm)
from .models import (Schedule, Department, DepartmentMembership, Employee, 
                     Vacation, RepeatUnavailability, DesiredTime, MonthlyRevenue,
                     Absence, BusinessData, LiveSchedule, LiveCalendar, 
                     DayNoteHeader, DayNoteBody, ScheduleSwapPetition, 
                     ScheduleSwapApplication)
from .business_logic import (get_eligibles, eligable_list_to_dict,
                             date_handler, all_calendar_hours_and_costs, 
                             get_avg_monthly_revenue, add_employee_cost_change,
                             remove_schedule_cost_change, create_live_schedules,
                             get_tro_dates, get_tro_dates_to_dict, time_dur_in_hours,
                             get_start_end_of_calendar, edit_schedule_cost_change,
                             calculate_cost_delta, get_start_end_of_weekday,
                             get_availability, _availability_to_dict)
from .forms import (CalendarForm, AddScheduleForm, ProtoScheduleForm, 
                    VacationForm, AbsentForm, RepeatUnavailabilityForm, 
                    DesiredTimeForm, MonthlyRevenueForm, BusinessDataForm, 
                    PushLiveForm, LiveCalendarForm, LiveCalendarManagerForm,
                    SetActiveStateLiveCalForm, ViewLiveCalendarForm, 
                    DepartmentMembershipForm, DayNoteHeaderForm, 
                    DayNoteBodyForm, ScheduleNoteForm, ScheduleSwapPetitionForm, 
                    ScheduleSwapDecisionForm, EditScheduleForm, CopySchedulesForm,
                    EmployeeDisplaySettingsForm, SetStateLiveCalForm)
from custom_mixins import UserIsManagerMixin
from datetime import datetime, date, time, timedelta
from itertools import chain
import bisect
import pytz
import json


def ssl_http(request):
    """http method for verifying SSL security cerftificate for NameCheap."""
    filename = "735B730461563A26284BCE64D8EE12C5.txt"
    content = '7219FE0C73F963798762C6D0968492E633BB373A52590DB4DDA354447E194D19 comodoca.com 5a96e2950377c'
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
    return response
    
    
def front_or_cal_page(request):
    """Redirect to calendar if logged in, otherwise redirect to front page."""
    if request.user.is_authenticated():
        if manager_check(request.user):
            return redirect("/calendar/") # Manager calendar
        else:
            return redirect("/live_calendar/") # Employee calendar
    else:
        return redirect("/front/")
        

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
        return redirect("/calendar/") # Manager calendar
    else:
        return redirect("/live_calendar/") # Employee calendar

        
def register(request):
    """Signup form for manager users"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            # Create business logic for user
            business_data = BusinessData(user=user)
            business_data.save()
            department = Department(user=user, name="Main")
            department.save()
            # Add user to manager group for permissions
            manager_user_group = Group.objects.get(name="Managers")
            user.groups.add(manager_user_group)
            # Log user in and redirect to department page to create 1st dep
            login(request, user)
            return redirect('/calendar/')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signUp.html', {'form': form})


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def calendar_page(request):
    """Display the schedule editing page for a managing user."""
    logged_in_user = request.user
    
    # Check that user has at least 1 department before loading calendar
    departments = Department.objects.filter(user=logged_in_user).order_by('name')
    if not departments:
        return redirect('/departments/')
    
    template = loader.get_template('schedulingcalendar/calendar.html')
    
    calendar_form = CalendarForm(logged_in_user)
    add_schedule_form = AddScheduleForm()
    view_live_form = ViewLiveCalendarForm()
    day_note_header_form = DayNoteHeaderForm()
    day_note_body_form = DayNoteBodyForm()
    schedule_note_form = ScheduleNoteForm()
    # If user has previously loaded a calendar, load that calendar. Otherwise,
    # load the current date and first department found in query
    business_data = BusinessData.objects.get(user=logged_in_user)
    if business_data.last_cal_date_loaded:
        date = business_data.last_cal_date_loaded
    else:
        date = datetime.now()
        
    if business_data.last_cal_department_loaded:
        department = business_data.last_cal_department_loaded
    else:
        department = departments.first()
        
    set_live_cal_form = SetStateLiveCalForm(logged_in_user, department)
        
    
    context = {'calendar_form': calendar_form, 
               'add_sch_form': add_schedule_form,
               'view_live_form': view_live_form,
               'set_live_cal_form': set_live_cal_form,
               'day_note_header_form': day_note_header_form,
               'day_note_body_form': day_note_body_form,
               'schedule_note_form': schedule_note_form,
               'date': date,
               'department': department.id,
               'departments': departments}

    return HttpResponse(template.render(context, request))
    
    
@login_required
def employee_calendar_page(request):
    """Display the schedule editing page for a managing user."""
    logged_in_user = request.user
    # Get manager corresponding to employee
    employee = (Employee.objects.select_related('user')
                                .get(employee_user=logged_in_user))
    employee_only = employee.see_only_my_schedules
    manager_user = employee.user
    
    live_calendar_form = LiveCalendarForm(manager_user, employee)
    template = loader.get_template('schedulingcalendar/employeeCalendar.html')
    context = {'live_calendar_form': live_calendar_form, 'employee_only': employee_only}

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
            cal_date = datetime(year, month, 1)
            lower_bound_dt, upper_bound_dt = get_start_end_of_calendar(year, month)
            
            # Get live_calendar to find out if calendar is active
            try:
              live_calendar = LiveCalendar.objects.get(user=logged_in_user, 
                                                       date=cal_date.date(), 
                                                       department=department_id)
              is_active = live_calendar.active
            except LiveCalendar.DoesNotExist:
              is_active = None;
            
            # Get schedule and employee models from database
            schedules = (Schedule.objects.select_related('employee')
                                         .filter(user=logged_in_user,
                                                 start_datetime__gte=lower_bound_dt,
                                                 end_datetime__lte=upper_bound_dt)
                                         .order_by('start_datetime', 'end_datetime'))

            employees = Employee.objects.filter(user=logged_in_user).order_by('first_name', 'last_name')
            dep_memberships = (DepartmentMembership.objects.filter(user=logged_in_user, department=department_id))
            employees_in_dep = []
            employee_ids = []
            for dep_mem in dep_memberships:
                employee_ids.append(dep_mem.employee.id)
            for e in employees:
                if e.id in employee_ids:
                    employees_in_dep.append(e)
                                                 
            # Check if any employees for this user exist to alert them if no employees exist
            # Or alert them if employees exist, but none are members of this department
            no_employees_exist = False
            no_employees_exist_for_department = False
            if not employees: 
                all_employees = Employee.objects.filter(user=logged_in_user)
                if not all_employees:
                    no_employees_exist = True
                else: # Employees exist, but none for this department
                    all_dep_employees = DepartmentMembership.objects.filter(department=department_id)
                    if not all_dep_employees:
                        no_employees_exist_for_department = True
                    
            # Get departments of user for manipulating parts of calendar view
            departments = Department.objects.filter(user=logged_in_user).order_by('name')
                    
            # Get day notes to display for dates within range of month
            day_note_header = DayNoteHeader.objects.filter(user=logged_in_user,
                                                           date__lte=upper_bound_dt,
                                                           date__gte=lower_bound_dt,
                                                           department=department_id)
            day_note_body = DayNoteBody.objects.filter(user=logged_in_user,
                                                       date__lte=upper_bound_dt,
                                                       date__gte=lower_bound_dt,
                                                       department=department_id)    

            # Get time requested off instances
            tro_dates = get_tro_dates(logged_in_user, department_id, lower_bound_dt, upper_bound_dt)
            tro_dict = get_tro_dates_to_dict(tro_dates)
                                                            
            # Convert schedules, employees and notes to dicts for json dump
            schedules_as_dicts = []
            employees_as_dicts = []
            departments_as_dicts = {}
            day_note_header_as_dicts = []
            day_note_body_as_dicts = []
            
            for s in schedules:
                if s.department.id == department_id:
                    schedule_dict = model_to_dict(s)
                    schedules_as_dicts.append(schedule_dict)
            for e in employees_in_dep:
                employee_dict = model_to_dict(e)
                employees_as_dicts.append(employee_dict) 
            for d in departments:
                departments_as_dicts[d.id] = d.name
            for day_hdr in day_note_header:
                day_hdr_dict = model_to_dict(day_hdr)
                day_note_header_as_dicts.append(day_hdr_dict)
            for day_body in day_note_body:
                day_body_dict = model_to_dict(day_body)
                day_note_body_as_dicts.append(day_body_dict)
            
            # Get business data for display settings on calendar
            business_data = BusinessData.objects.get(user=logged_in_user)
            business_dict = model_to_dict(business_data)
            
            # Use business data to remember last calendar loaded by user
            business_data.last_cal_date_loaded = cal_date
            department = Department.objects.get(pk=department_id)
            business_data.last_cal_department_loaded = department
            business_data.save()
            
            # Get calendar costs to display to user
            hours_and_costs = all_calendar_hours_and_costs(logged_in_user, departments, schedules, employees, month, year, business_data)
            avg_monthly_revenue = get_avg_monthly_revenue(logged_in_user, month)
              
            # Combine all appropriate data into dict for serialization
            combined_dict = {'date': cal_date.isoformat(),
                             'department': department_id,
                             'departments': departments_as_dicts,
                             'schedules': schedules_as_dicts,
                             'employees': employees_as_dicts,
                             'day_note_header': day_note_header_as_dicts,
                             'day_note_body': day_note_body_as_dicts,
                             'tro_dates': tro_dict,
                             'hours_and_costs': hours_and_costs,
                             'avg_monthly_revenue': avg_monthly_revenue,
                             'display_settings': business_dict,
                             'is_active': is_active,
                             'no_employees_exist': no_employees_exist,
                             'no_employees_exist_for_department': no_employees_exist_for_department}
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
            employee_user_pk = None
            override_list_view = False
            manager_user = logged_in_user
            form = LiveCalendarManagerForm(manager_user, 1, request.GET)
        else:
            employee = (Employee.objects.select_related('user')
                                .get(employee_user=logged_in_user))
            employee_user_pk = employee.id
            override_list_view = employee.override_list_view
            manager_user = employee.user
            form = LiveCalendarForm(manager_user, employee, request.GET)
        if form.is_valid():
            department_id = form.cleaned_data['department']
            year = form.cleaned_data['year']
            month = form.cleaned_data['month']
            cal_date = datetime(year, month, 1)
            lower_bound_dt, upper_bound_dt = get_start_end_of_calendar(year, month)
            
            try:
                live_calendar = LiveCalendar.objects.get(user=manager_user, 
                                                         date=cal_date, 
                                                         department=department_id)
                if not live_calendar.active:
                    raise ValueError('Live Calendar exists, but is not active.')
                                                         
                # LiveCalendarManagerForm form does not have employee only option,
                # so we set it to false so manager sees all schedules for calendar
                # Employees always get the latest version of the live calendar
                if user_is_manager:
                    employee_only = False
                    version = form.cleaned_data['version']
                else:
                    employee_only = form.cleaned_data['employee_only']
                    employee.see_only_my_schedules = employee_only
                    employee.save()
                    version = live_calendar.version
                    
                # Get schedule and employee models from database appropriate for calendar
                if employee_only:
                    live_schedules = (LiveSchedule.objects.select_related('employee')
                                                  .filter(user=manager_user,
                                                          employee=employee,
                                                          calendar=live_calendar,
                                                          version=version))
                else: 
                    live_schedules = (LiveSchedule.objects.select_related('employee')
                                                  .filter(user=manager_user,
                                                          calendar=live_calendar,
                                                          version=version))
                                                          
                # Get employees
                dep_memberships = (DepartmentMembership.objects.filter(user=manager_user, department=department_id))
                employee_ids = []
                for dep_mem in dep_memberships:
                    employee_ids.append(dep_mem.employee.id)
                employees = (Employee.objects.filter(user=manager_user, id__in=employee_ids)
                                             .order_by('first_name', 'last_name'))
                                             
                # Get time requested off instances
                tro_dates = get_tro_dates(manager_user, department_id, lower_bound_dt, upper_bound_dt)
                tro_dict = get_tro_dates_to_dict(tro_dates)
                        
                # Get day notes to display for dates within range of month
                day_note_header = DayNoteHeader.objects.filter(user=manager_user,
                                                               date__lte=upper_bound_dt,
                                                               date__gte=lower_bound_dt,
                                                               department=department_id)
                day_note_body = DayNoteBody.objects.filter(user=manager_user,
                                                           date__lte=upper_bound_dt,
                                                           date__gte=lower_bound_dt,
                                                           department=department_id)  
                
                # Convert live_schedules and employees to dicts for json dump
                schedules_as_dicts = []
                employees_as_dicts = []
                day_note_header_as_dicts = []
                day_note_body_as_dicts = []
                
                for s in live_schedules:
                    schedule_dict = model_to_dict(s)
                    schedules_as_dicts.append(schedule_dict)
                for e in employees:
                    employee_dict = model_to_dict(e)
                    employees_as_dicts.append(employee_dict)
                for day_hdr in day_note_header:
                    day_hdr_dict = model_to_dict(day_hdr)
                    day_note_header_as_dicts.append(day_hdr_dict)
                for day_body in day_note_body:
                    day_body_dict = model_to_dict(day_body)
                    day_note_body_as_dicts.append(day_body_dict)
                
                # Get business data for display settings on calendar
                business_data = (BusinessData.objects.get(user=manager_user))
                business_dict = model_to_dict(business_data)
                  
                # Combine all appropriate data into dict for serialization
                combined_dict = {'date': cal_date.isoformat(), 
                                 'department': department_id,
                                 'schedules': schedules_as_dicts,
                                 'employees': employees_as_dicts,
                                 'day_note_header': day_note_header_as_dicts,
                                 'day_note_body': day_note_body_as_dicts,
                                 'tro_dates': tro_dict,
                                 'version': version,
                                 'display_settings': business_dict,
                                 'employee_user_pk': employee_user_pk,
                                 'override_list_view': override_list_view,
                                 'lower_bound_dt': lower_bound_dt.isoformat(),
                                 'upper_bound_dt': upper_bound_dt.isoformat()}
                combined_json = json.dumps(combined_dict, default=date_handler)
                
                return JsonResponse(combined_json, safe=False)
                
            except (LiveCalendar.DoesNotExist, ValueError) as error:
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
            
            # Save time and hide choices to business settings
            business_data = BusinessData.objects.get(user=logged_in_user)
            business_data.schedule_start = start_time
            business_data.schedule_end = end_time
            business_data.hide_start = hide_start
            business_data.hide_end = hide_end
            business_data.save()
            
            # Construct start and end datetimes for schedule
            time_zone = timezone.get_default_timezone_name()
            start_dt = datetime.combine(date, start_time)
            start_dt = pytz.timezone(time_zone).localize(start_dt)
            end_dt = datetime.combine(date, end_time)
            end_dt = pytz.timezone(time_zone).localize(end_dt)

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
    
    eligable_list = get_eligibles(logged_in_user, schedule)
    eligable_dict_list = eligable_list_to_dict(eligable_list)
    json_data = json.dumps(eligable_dict_list, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def get_proto_schedule_info(request):
    """Get eligible list for onChange response to add_schedule_form.
    
    This function is used to create a mock schedule to see what the eligible
    list would be IF a user created a schedule with said parameters. It informs
    the user what employee options they would have if they created the schedule.
    """
    
    logged_in_user = request.user
    if request.method == 'GET':
        form = ProtoScheduleForm(request.GET)
        if form.is_valid():
            department = form.cleaned_data['department']
            date = form.cleaned_data['add_date']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            
            # Construct start and end datetimes for schedule
            time_zone = timezone.get_default_timezone_name()
            start_dt = datetime.combine(date, start_time)
            start_dt = pytz.timezone(time_zone).localize(start_dt)
            end_dt = datetime.combine(date, end_time)
            end_dt = pytz.timezone(time_zone).localize(end_dt)

            # TODO: Assert department belongs to user after form cleaning?
            dep = Department.objects.get(user=logged_in_user, pk=department)
            schedule = Schedule(user=logged_in_user,
                                start_datetime=start_dt, end_datetime=end_dt,
                                department=dep)
            
            eligable_list = get_eligibles(logged_in_user, schedule)
            eligable_dict_list = eligable_list_to_dict(eligable_list)
            json_data = json.dumps(eligable_dict_list, default=date_handler)
            
            return JsonResponse(json_data, safe=False)
    else:
        # TODO: Case where invalid HTTP Request handling
        pass
    
    
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
    
    # Get length of schedule for new employee, and old employee if exists
    new_sch_duration = time_dur_in_hours(schedule.start_datetime, schedule.end_datetime, 
                                         None, None, min_time_for_break=new_employee.min_time_for_break,
                                         break_time_in_min=new_employee.break_time_in_min)
    old_sch_duration = 0
    if schedule.employee:
        prev_employee = schedule.employee
        old_sch_duration = time_dur_in_hours(schedule.start_datetime, schedule.end_datetime, 
                                             None, None, min_time_for_break=prev_employee.min_time_for_break,
                                             break_time_in_min=prev_employee.break_time_in_min)
    
    # Assign new employee to schedule
    schedule.employee = new_employee
    schedule.save(update_fields=['employee'])
    
    # Process information for json dump
    schedule_dict = model_to_dict(schedule)
    employee_dict = model_to_dict(new_employee)
    data = {'schedule': schedule_dict, 'employee': employee_dict, 
            'cost_delta': cost_delta, 'new_sch_duration': new_sch_duration,
            'old_sch_duration': old_sch_duration}
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
                                
    cost_delta = 0
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
def edit_schedule(request):
    """Edit start/end times and hide start/end booleans for schedule."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = EditScheduleForm(request.POST)
        if form.is_valid():
            schedule_pk = form.cleaned_data['schedule_pk']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            hide_start = form.cleaned_data['hide_start']
            hide_end = form.cleaned_data['hide_end']
            cal_date = form.cleaned_data['cal_date']
            # User is undoing previous edit to this schedule, in case schedule had conflict
            # before edit, don't send any conflict to avoid infinite loop of warnings
            undo_edit = form.cleaned_data['undo_edit']
            schedule = (Schedule.objects.select_related('department', 'employee')
                                        .get(user=logged_in_user, pk=schedule_pk))
                                        
            old_start_dt = schedule.start_datetime.isoformat()
            old_end_dt = schedule.end_datetime.isoformat()  
            oldHideStart = schedule.hide_start_time
            oldHideEnd = schedule.hide_start_time
            
            # Construct start and end datetimes for schedule
            date = schedule.start_datetime.date()
            time_zone = timezone.get_default_timezone_name()
            start_dt = datetime.combine(date, start_time)
            start_dt = pytz.timezone(time_zone).localize(start_dt)
            end_dt = datetime.combine(date, end_time)
            end_dt = pytz.timezone(time_zone).localize(end_dt)
            
            # Get cost difference of changing schedule time if employee assigned
            cost_delta = 0
            old_sch_duration = 0
            new_sch_duration = 0
            if schedule.employee:
                # Calculate cost difference from editing times:
                departments = Department.objects.filter(user=logged_in_user)
                business_data = BusinessData.objects.get(user=logged_in_user)
                cost_delta = edit_schedule_cost_change(logged_in_user, schedule,
                                                       start_dt, end_dt,
                                                       departments, business_data,
                                                       cal_date)
                                                       
                # Get length of schedule for new employee, and old employee if exists
                old_sch_duration = time_dur_in_hours(schedule.start_datetime, schedule.end_datetime, 
                                                     None, None, min_time_for_break=schedule.employee.min_time_for_break,
                                                     break_time_in_min=schedule.employee.break_time_in_min)
                new_sch_duration = time_dur_in_hours(start_dt, end_dt, 
                                                     None, None, min_time_for_break=schedule.employee.min_time_for_break,
                                                     break_time_in_min=schedule.employee.break_time_in_min)
                                   
            # Save time and hide choices to business settings
            business_data = BusinessData.objects.get(user=logged_in_user)
            business_data.schedule_start = start_time
            business_data.schedule_end = end_time
            business_data.hide_start = hide_start
            business_data.hide_end = hide_end
            business_data.save()
            
            #Set schedule fields to form data
            schedule.start_datetime = start_dt
            schedule.end_datetime = end_dt
            schedule.hide_start_time = hide_start
            schedule.hide_end_time = hide_end                 
            schedule.save()
            
            # Check for any conflicts with new schedule times if employee assigned
            availability = {}
            if schedule.employee and not undo_edit:
                new_availability = get_availability(logged_in_user, schedule.employee, schedule)
                other_sch = new_availability['(S)']
                vacation = new_availability['(V)']
                unavail = new_availability['(A)']
                repeat_unavail = new_availability['(U)']
                overtime = new_availability['(O)']
                if other_sch or vacation or unavail or repeat_unavail or overtime:
                    availability = _availability_to_dict(new_availability)
            
            schedule_dict = model_to_dict(schedule)
            json_info = json.dumps({'schedule': schedule_dict,
                                    'cost_delta': cost_delta,
                                    'new_sch_duration': new_sch_duration,
                                    'old_sch_duration': old_sch_duration,
                                    'availability': availability, 
                                    'oldStartDatetime': old_start_dt,
                                    'oldEndDatetime': old_end_dt,
                                    'oldHideStart': oldHideStart, 
                                    'oldHideEnd': oldHideEnd},
                                    default=date_handler)
            return JsonResponse(json_info, safe=False)
            
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")    
def copy_schedules(request):
    """Copy set of schedules pks with given date."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = CopySchedulesForm(request.POST)
        if form.is_valid():
            schedule_pks = form.cleaned_data['schedule_pks']
            date = form.cleaned_data['date']
            cal_date = form.cleaned_data['cal_date']
            schedules = (Schedule.objects.select_related('employee')
                                         .filter(user=logged_in_user, id__in=schedule_pks))
            
            # Calculate cost of workweek before adding schedules 
            employees = []
            for sch in schedules:
                if sch.employee:
                    employees.append(sch.employee)
            departments = Department.objects.filter(user=logged_in_user)
            business_data = BusinessData.objects.get(user=logged_in_user)
            time_zone = timezone.get_default_timezone_name()
            date_as_datetime = datetime.combine(date, time(12))
            date_as_datetime = pytz.timezone(time_zone).localize(date_as_datetime)
            workweek = get_start_end_of_weekday(date_as_datetime, logged_in_user)
            workweek_schedules = (Schedule.objects.select_related('department', 'employee')
                                          .filter(user=logged_in_user,
                                                  end_datetime__gt=workweek['start'],
                                                  start_datetime__lt=workweek['end'],
                                                  employee__in=employees)
                                          .order_by('start_datetime', 'end_datetime'))
            workweek_schedules = [sch for sch in workweek_schedules]
            old_week_cost = 0
            if workweek_schedules:
                old_week_cost = all_calendar_hours_and_costs(logged_in_user, departments,
                                                             workweek_schedules, [], 
                                                             cal_date.month, cal_date.year, 
                                                             business_data, workweek)
                                                             
            # Create copied schedules and get availability of copied schedules with employees
            # We only add the availability if there is a conflict between employee and schedules
            schedule_availabilities = {}                       
            copied_schedules = []
            for sch in schedules:
                new_start_dt = sch.start_datetime.replace(year=date.year, month=date.month, day=date.day)
                new_end_dt = sch.end_datetime.replace(year=date.year, month=date.month, day=date.day)
                copy_schedule = Schedule(user=logged_in_user,
                                         start_datetime=new_start_dt, 
                                         end_datetime=new_end_dt,
                                         hide_start_time=sch.hide_start_time,
                                         hide_end_time=sch.hide_end_time,
                                         schedule_note=sch.schedule_note,
                                         department=sch.department,
                                         employee=sch.employee)
                copy_schedule.save()
                copied_schedules.append(copy_schedule)
                
                if copy_schedule.employee:
                    availability = get_availability(logged_in_user, copy_schedule.employee, copy_schedule)
                    other_sch = availability['(S)']
                    vacation = availability['(V)']
                    unavail = availability['(A)']
                    repeat_unavail = availability['(U)']
                    overtime = availability['(O)']
                    
                    if other_sch or vacation or unavail or repeat_unavail or overtime:
                        schedule_availabilities[copy_schedule.id] = availability
                
            # Calculate cost of workweek with new copied schedules
            for schedule in copied_schedules:
                if schedule.employee:
                    bisect.insort_left(workweek_schedules, schedule)
            new_week_cost = all_calendar_hours_and_costs(logged_in_user, departments,
                                                         workweek_schedules, [], 
                                                         cal_date.month, cal_date.year, 
                                                         business_data, workweek)
            if old_week_cost:
                cost_delta = calculate_cost_delta(old_week_cost, new_week_cost, 'subtract')
            else:
                cost_delta = new_week_cost
                
            # Serialize data
            availability_as_dicts = {}
            for avail in schedule_availabilities:
                avail_dict = _availability_to_dict(schedule_availabilities[avail])
                availability_as_dicts[avail] = avail_dict
            
            schedules_as_dicts = []
            for s in copied_schedules:
                schedule_dict = model_to_dict(s)
                schedules_as_dicts.append(schedule_dict)
            
            json_info = json.dumps({'schedules': schedules_as_dicts, 'cost_delta': cost_delta, 
                                    'availability': availability_as_dicts},
                                    default=date_handler)
            return JsonResponse(json_info, safe=False)
    
    json_info = json.dumps({'schedule_pks': "failed to do anything", 'cost_delta': 0},
                            default=date_handler)
    return JsonResponse(json_info, safe=False)
    
   
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")    
def remove_conflict_copy_schedules(request):
    """Remove copied schedules that have conflict user did not want to keep."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = CopySchedulesForm(request.POST)
        if form.is_valid():
            schedule_pks = form.cleaned_data['schedule_pks']
            date = form.cleaned_data['date']
            cal_date = form.cleaned_data['cal_date']
            schedules = (Schedule.objects.select_related('employee')
                                         .filter(user=logged_in_user, id__in=schedule_pks))
            
            # Get cost delta from removing each schedule then delete schedule
            departments = Department.objects.filter(user=logged_in_user)
            business_data = BusinessData.objects.get(user=logged_in_user)
            total_cost_delta = {}
            for sch in schedules:
                if sch.employee:
                    cost_delta = remove_schedule_cost_change(logged_in_user, sch,
                                                             departments, business_data,
                                                             cal_date)                                      
                    if not total_cost_delta:
                        total_cost_delta = cost_delta
                    else:
                        total_cost_delta = calculate_cost_delta(total_cost_delta, cost_delta, 'add')
                        
                    sch.delete()
                        
            # Return cost delta to front end to be rendered    
            json_info = json.dumps({'cost_delta': cost_delta}, default=date_handler)      
            return JsonResponse(json_info, safe=False)

            
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def push_changes_live(request):
    """Create a live version of schedules for employee users to query."""
    logged_in_user = request.user
    if request.method == 'POST':
        print
        print
        print "*********** request.POST is: ", request.POST

        form = SetStateLiveCalForm(logged_in_user, None, request.POST)
        print "********** is form valid? ", form.is_valid()
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
                live_calendar.active = True
                live_calendar.version += 1
                live_calendar.save()
                create_live_schedules(logged_in_user, live_calendar)
                
            json_info = json.dumps({'message': 'Successfully pushed calendar live!'})
            return JsonResponse(json_info, safe=False)
        
        json_info = json.dumps({'message': 'Failed to push calendar live.'})
        return JsonResponse(json_info, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests
        
        
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def set_active_state(request):
    """Deactivate or reactivate the live_calendar for given month"""
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
                  message = 'Successfully reactivated the live calendar!'
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
        if form.is_valid():
            date = form.cleaned_data['date']
            department_id = form.cleaned_data['department']
            try: # Get live_calendar to find out if calendar is active
                live_calendar = LiveCalendar.objects.get(user=logged_in_user, 
                                                         date=date, 
                                                         department=department_id)
                is_active = live_calendar.active
                if is_active:
                    template = loader.get_template('schedulingcalendar/managerCalendar.html')
                    live_calendar_form = LiveCalendarManagerForm(logged_in_user,
                                                                 live_calendar.version)
                    department = Department.objects.get(pk=department_id)
                    context = {'live_calendar_form': live_calendar_form,
                               'date': date,
                               'department': department_id,
                               'version': live_calendar.version,
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
        
        
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def add_edit_day_note_header(request): 
    """Add or edit a day note header."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = DayNoteHeaderForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['header_text']
            date = form.cleaned_data['date']
            dep =  form.cleaned_data['department']
            day_note_header, created = DayNoteHeader.objects.get_or_create(user=logged_in_user,
                                                                           date=date,
                                                                           department=dep)
            day_note_header.header_text = text
            day_note_header.save(update_fields=['header_text'])
            day_note_header_dict = model_to_dict(day_note_header)
            day_note_header_json = json.dumps(day_note_header_dict, default=date_handler)
            
            return JsonResponse(day_note_header_json, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests    

        
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def add_edit_day_note_body(request): 
    """Add or edit a day note body."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = DayNoteBodyForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['body_text']
            date = form.cleaned_data['date']
            dep =  form.cleaned_data['department']
            day_note_body, created = DayNoteBody.objects.get_or_create(user=logged_in_user,
                                                                       date=date,
                                                                       department=dep)
            day_note_body.body_text = text
            day_note_body.save(update_fields=['body_text'])
            day_note_body_dict = model_to_dict(day_note_body)
            day_note_body_json = json.dumps(day_note_body_dict, default=date_handler)
            
            return JsonResponse(day_note_body_json, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests    
        
        
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def edit_schedule_note(request): 
    """Add or edit a day note body."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = ScheduleNoteForm(request.POST)
        if form.is_valid():
            id = form.cleaned_data['schedule_pk']
            text = form.cleaned_data['schedule_text']
            schedule = Schedule.objects.get(user=logged_in_user, pk=id)
            schedule.schedule_note = text
            schedule.save(update_fields=['schedule_note'])
            
            schedule_dict = model_to_dict(schedule)
            schedule_json = json.dumps(schedule_dict, default=date_handler)
            
            return JsonResponse(schedule_json, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests    
        
        
@login_required
def create_schedule_swap_petition(request):
    """Create schedule petition swap for logged in employee"""
    logged_in_user = request.user
    if request.method == 'POST':
        form = ScheduleSwapPetitionForm(request.POST)
        if form.is_valid():
            id = form.cleaned_data['live_schedule_pk']
            note = form.cleaned_data['note']
            employee = (Employee.objects.select_related('user')
                                .get(employee_user=logged_in_user))
            manager_user = employee.user
            live_schedule = LiveSchedule.objects.get(user=manager_user,
                                                     employee=employee,
                                                     pk=id)
            
            schedule_swap_petition = ScheduleSwapPetition(user=manager_user,
                                                          live_schedule=live_schedule,
                                                          employee=employee,
                                                          note=note)
            schedule_swap_petition.save()
            
            json_info = json.dumps({'message': 'Successfully created schedule swap petition!'})
            return JsonResponse(json_info, safe=False)
    else:
        pass
        #TODO: Implement reponse for non-POST requests    
        json_info = json.dumps({'message': 'Could not create schedule swap petition'})
        return JsonResponse(json_info, safe=False)
        

@login_required 
@user_passes_test(manager_check, login_url="/live_calendar/")       
def pending_approvals_page(request):
    """Display the manager's pending approval page"""
    template = loader.get_template('schedulingcalendar/managerPendingApprovals.html')
    logged_in_user = request.user
    
    schedule_swaps = ScheduleSwapPetition.objects.filter(user=logged_in_user, approved__isnull=True)

    context = {'sch_swap_list': schedule_swaps}
    return HttpResponse(template.render(context, request))
    
    
@login_required 
@user_passes_test(manager_check, login_url="/live_calendar/")
def schedule_swap_disapproval(request):
    """Set schedule swap petition to disapproved and notify corresponding employees."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = ScheduleSwapDecisionForm(request.POST)
        if form.is_valid():
            # TODO: Notify employee via email/text
            schedule_swap_pk = form.cleaned_data['schedule_swap_pk']
            
            schedule_swap = ScheduleSwapPetition.objects.get(user=logged_in_user,
                                                             pk=schedule_swap_pk)
            schedule_swap.approved = False
            schedule_swap.save()
            sch_swap_apps = (ScheduleSwapApplication.objects
                                                    .filter(user=logged_in_user,
                                                            schedule_swap_petition=schedule_swap)
                                                    .update(approved=False))
            
            json_info = json.dumps({'message': 'Successfully disapproved schedule swap.',
                                    'sch_swap_id': schedule_swap_pk})
            return JsonResponse(json_info, safe=False)
    
    else:
        #TODO: Implement reponse for non-POST requests    
        json_info = json.dumps({'message': 'Could not disapprove schedule swap petition'})
        return JsonResponse(json_info, safe=False)
        
        
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
    fields = ['first_name', 'last_name', 'employee_id', 'email',
              'wage', 'desired_hours', 'monthly_medical', 
              'social_security', 'min_time_for_break',
              'break_time_in_min']
    
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
    fields = ['first_name', 'last_name', 'employee_id', 'email',
              'wage', 'desired_hours', 'monthly_medical', 
              'social_security', 'min_time_for_break',
              'break_time_in_min']
              
              
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
        

        
    