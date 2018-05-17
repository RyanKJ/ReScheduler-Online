from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from ..models import (Schedule, Department, DepartmentMembership, Employee, 
                     BusinessData, LiveSchedule, LiveCalendar, 
                     ScheduleSwapPetition, ScheduleSwapApplication)
from ..business_logic import (get_eligibles, all_calendar_hours_and_costs, 
                             get_avg_monthly_revenue, add_employee_cost_change,
                             remove_schedule_cost_change, create_live_schedules,
                             get_tro_dates, time_dur_in_hours, get_start_end_of_calendar, 
                             edit_schedule_cost_change, calculate_cost_delta, 
                             get_start_end_of_weekday, get_availability, get_dates_in_week,
                             set_view_rights, send_employee_texts, 
                             view_right_send_employee_texts)            
from ..forms import ScheduleSwapPetitionForm, ScheduleSwapDecisionForm
from ..serializers import get_json_err_response
from .views_basic_pages import manager_check
from datetime import datetime, date, time
import json

     
        
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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)
        

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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)