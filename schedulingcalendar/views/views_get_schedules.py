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
from django.views.generic import (View, ListView, FormView, CreateView, UpdateView, 
                                  DeleteView)
from django.contrib.auth.forms import (UserCreationForm, PasswordChangeForm, 
                                       SetPasswordForm)
from .models import (Schedule, Department, DepartmentMembership, Employee, 
                     Vacation, RepeatUnavailability, DesiredTime, MonthlyRevenue,
                     Absence, BusinessData, LiveSchedule, LiveCalendar, 
                     DayNoteHeader, DayNoteBody, ScheduleSwapPetition, 
                     ScheduleSwapApplication, LiveCalendarDepartmentViewRights,
                     LiveCalendarEmployeeViewRights)
from business_logic import (get_eligibles, all_calendar_hours_and_costs, 
                             get_avg_monthly_revenue, add_employee_cost_change,
                             remove_schedule_cost_change, create_live_schedules,
                             get_tro_dates, time_dur_in_hours, get_start_end_of_calendar, 
                             edit_schedule_cost_change, calculate_cost_delta, 
                             get_start_end_of_weekday, get_availability, get_dates_in_week,
                             set_view_rights, send_employee_texts, 
                             view_right_send_employee_texts)            
from .forms import (CalendarForm, AddScheduleForm, ProtoScheduleForm, 
                    VacationForm, AbsentForm, RepeatUnavailabilityForm, 
                    DesiredTimeForm, MonthlyRevenueForm, BusinessDataForm, 
                    LiveCalendarForm, LiveCalendarManagerForm, ViewLiveCalendarForm, 
                    DepartmentMembershipForm, DayNoteHeaderForm, 
                    DayNoteBodyForm, ScheduleNoteForm, ScheduleSwapPetitionForm, 
                    ScheduleSwapDecisionForm, EditScheduleForm, CopySchedulesForm,
                    EmployeeDisplaySettingsForm, SetStateLiveCalForm,
                    CalendarDisplaySettingsForm, SchedulePkForm, AddEmployeeToScheduleForm, 
                    RemoveScheduleForm)
from .serializers import (date_handler, get_json_err_response, eligable_list_to_dict,
                          get_tro_dates_to_dict, _availability_to_dict)
from custom_mixins import UserIsManagerMixin
from datetime import datetime, date, time, timedelta
from itertools import chain
import bisect
import pytz
import json
import copy



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
            
            # Get live_calendar to find out if calendar exists and view rights
            try:
              live_calendar = LiveCalendar.objects.get(user=logged_in_user, 
                                                       date=cal_date.date(), 
                                                       department=department_id)
              live_cal_exists = True
              view_rights = {'all_employee_view': live_calendar.all_employee_view, 
                             'department_view': [],
                             'employee_view': []}        
              
              department_view_rights = LiveCalendarDepartmentViewRights.objects.filter(user=logged_in_user, live_calendar=live_calendar)
              employee_view_rights = LiveCalendarEmployeeViewRights.objects.filter(user=logged_in_user, live_calendar=live_calendar)
              
              for dep_view_right in department_view_rights:
                  view_rights['department_view'].append(dep_view_right.department_view_rights.id)
              for emp_view_right in employee_view_rights:
                  view_rights['employee_view'].append(emp_view_right.employee_view_rights.id)
              
            except LiveCalendar.DoesNotExist:
                live_cal_exists = False
                view_rights = {}
            
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
                             'no_employees_exist': no_employees_exist,
                             'no_employees_exist_for_department': no_employees_exist_for_department,
                             'live_cal_exists': live_cal_exists,
                             'view_rights': view_rights}
            combined_json = json.dumps(combined_dict, default=date_handler)
            
            return JsonResponse(combined_json, safe=False)
            
        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
      msg = 'HTTP request needs to be GET. Got: ' + request.method
      return get_json_err_response(msg)

  
@login_required  
@user_passes_test(manager_check, login_url="/live_calendar/")
def get_live_schedules(request):
    """Get live schedules for given date and department as a manager."""
    logged_in_user = request.user
    if request.method == 'GET':
        manager_user = logged_in_user
        form = LiveCalendarManagerForm(manager_user, 1, request.GET)
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

                version = form.cleaned_data['version']
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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
      msg = 'HTTP request needs to be GET. Got: ' + request.method
      return get_json_err_response(msg)
      
      
@login_required  
def employee_get_live_schedules(request):
    """Get live schedules for given date and department as an employee."""
    logged_in_user = request.user
    if request.method == 'GET':
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
                # Check viewing rights of employee 
                if not live_calendar.all_employee_view:
                    has_view_right = False
                    
                    # Check if employee belongs to oldDepartmentViewRights
                    departments_of_employee = DepartmentMembership.objects.filter(user=manager_user, employee=employee)
                    department_view_rights = LiveCalendarDepartmentViewRights.objects.filter(user=manager_user, live_calendar=live_calendar)
                    employee_view_rights = LiveCalendarEmployeeViewRights.objects.filter(user=manager_user, live_calendar=live_calendar)
                    
                    for dep_view_right in department_view_rights:
                        for dep_mem_of_employee in departments_of_employee:
                            if dep_view_right.department_view_rights == dep_mem_of_employee.department:
                                has_view_right = True
                                break
                    # If not check if employee belongs to oldEmployeeViewRights
                    for emp_view_right in employee_view_rights:
                        if emp_view_right.employee_view_rights == employee:
                            has_view_right = True
                            break
                
                    if not has_view_right:
                        raise ValueError('Live Calendar exists, but employee cannot see.')
                    
                    
                                                         
                # Check if employee wishes to see only their schedules
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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
      msg = 'HTTP request needs to be GET. Got: ' + request.method
      return get_json_err_response(msg)