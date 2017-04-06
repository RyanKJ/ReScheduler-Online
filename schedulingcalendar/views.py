from django.core import serializers
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from django.template import loader
from django.contrib.auth.decorators import login_required
from .models import Schedule, Department, Employee
from django.forms.models import model_to_dict
from business_logic import get_eligables, eligable_list_to_dict, date_handler, yearify
from datetime import datetime, date, timedelta
from itertools import chain
import json


@login_required
def index(request):
    logged_in_user = request.user
    now = datetime.now()
    current_year = now.year
    year_list = yearify(current_year, 5)
    
    # TODO: Add edge case where user has 0 departments
    department_list = Department.objects.filter(user=logged_in_user)
    template = loader.get_template('schedulingcalendar/index.html')
    context = {
        'department_list': department_list,
        'year_list': year_list
    }
    
    return HttpResponse(template.render(context, request))

    
@login_required
def get_schedules(request):
    logged_in_user = request.user
    year = request.GET['year']
    month = request.GET['month']
    department_id = request.GET['department']
    # Get date month for calendar for queries
    cal_date = datetime.strptime(year + month, "%Y%m")
    lower_bound_dt = cal_date - timedelta(7)
    upper_bound_dt = cal_date + timedelta(42)
    
    # Get schedule and employee models from database appropriate for calendar
    schedules = (Schedule.objects.select_related('employee')
                                 .filter(user=logged_in_user)
                                 .filter(start_datetime__gte=lower_bound_dt)
                                 .filter(end_datetime__lte=upper_bound_dt)
                                 .filter(department=department_id)
                )
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
        
    # Combine all appropriate data into dict for serialization
    combined_dict = {'date': cal_date.isoformat(), 
                     'department': department_id,
                     'schedules': schedules_as_dicts,
                     'employees': employees_as_dicts}
    combined_json = json.dumps(combined_dict, default=date_handler)
    return JsonResponse(combined_json, safe=False)

    
@login_required
def add_schedule(request):
    """Add schedule to the database and return string of added schedule."""
    try:
        logged_in_user = request.user
        date = request.POST['date']
        department = request.POST['department']
        start_time = request.POST['start-timepicker']
        end_time = request.POST['end-timepicker']
        
        start_str = date + " " + start_time
        end_str = date + " " + end_time

        str_format = '%Y-%m-%d %I:%M %p'
        start = datetime.strptime(start_str, str_format)
        end = datetime.strptime(end_str, str_format)
        
        # TODO: Way to parse response such that this processing is redundant?
        s_hide = request.POST['hide-start']
        if s_hide == 'True':
            s_hide = True
        else:
            s_hide = False
        e_hide = request.POST['hide-end']
        if e_hide == 'True':
            e_hide = True
        else:
            e_hide = False
        dep = Department.objects.get(user=logged_in_user, pk=department)
        schedule = Schedule(user=logged_in_user,
                            start_datetime=start, end_datetime=end,
                            hide_start_time=s_hide,
                            hide_end_time=e_hide,
                            department=dep)
    except (KeyError):
        # Redisplay the question voting form.
        return render(request, 'schedulingcalendar/index.html', {
            'error_message': "Something went wrong. Beep. Boop. Bop. flop...",
        })
    else:
        schedule.save()
        schedule_dict = model_to_dict(schedule)
        schedule_json = json.dumps(schedule_dict, default=date_handler)
        
        return JsonResponse(schedule_json, safe=False)
        
     
@login_required     
def get_schedule_info(request):
    """Returns information for schedule such as eligable employees."""
    logged_in_user = request.user
    schedule_pk = request.GET['pk']
    schedule = Schedule.objects.get(user=logged_in_user, pk=schedule_pk)
    
    
    eligable_list = get_eligables(schedule)
    eligable_dict_list = eligable_list_to_dict(eligable_list)
    json_data = json.dumps(eligable_dict_list, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    

@login_required
def add_employee_to_schedule(request):
    logged_in_user = request.user
    schedule_pk = request.POST['schedule_pk']
    employee_pk = request.POST['employee_pk']
    schedule = Schedule.objects.get(user=logged_in_user, pk=schedule_pk)
    employee = Employee.objects.get(user=logged_in_user, pk=employee_pk)

    schedule.employee = employee
    schedule.save(update_fields=['employee'])
    
    schedule_dict = model_to_dict(schedule)
    employee_dict = model_to_dict(employee)
    data = {'schedule': schedule_dict, 'employee': employee_dict}
    json_data = json.dumps(data, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    

@login_required
def remove_schedule(request):
    logged_in_user = request.user
    schedule_pk = request.POST['schedule_pk']
    schedule = Schedule.objects.get(user=logged_in_user, pk=schedule_pk)
    schedule.delete()
    
    json_info = json.dumps({'schedule_pk': schedule_pk}, default=date_handler)
    return JsonResponse(json_info, safe=False)
    
    
    