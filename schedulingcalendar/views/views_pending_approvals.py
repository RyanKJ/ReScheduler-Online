from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template import loader
from ..models import (Schedule, Department, DepartmentMembership, Employee,
                     BusinessData, LiveSchedule, LiveCalendar,
                     ScheduleSwapPetition, ScheduleSwapApplication)
from ..business_logic import (get_eligibles, all_calendar_hours_and_costs,
                             get_avg_monthly_revenue, add_employee_cost_change,
                             remove_schedule_cost_change, create_live_schedules,
                             get_tro_dates, time_dur_in_hours, get_start_end_of_calendar,
                             edit_schedule_cost_change, calculate_cost_delta,
                             get_start_end_of_weekday, get_availability, get_dates_in_week,
                             notify_employee_with_msg)            
from ..forms import ScheduleSwapPetitionForm, ScheduleSwapDecisionForm, PkForm
from ..models import (VacationApplication, AbsenceApplication, RepeatUnavailabilityApplication,
                      Vacation, Absence, RepeatUnavailability)
from ..serializers import get_json_err_response
from .views_basic_pages import manager_check
from datetime import datetime, date, time
import json


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")  
def pending_approvals_page(request):
    """Display the pending approvals page for a managing user."""
    logged_in_user = request.user
    
    template = loader.get_template('schedulingcalendar/pendingApprovals.html')
    context = {}
    
    vacation_apps = (VacationApplication.objects.select_related('employee')
                                                .filter(user=logged_in_user, approved=None))
    absence_apps = (AbsenceApplication.objects.select_related('employee')
                                              .filter(user=logged_in_user, approved=None))
    repeat_unav_apps = (RepeatUnavailabilityApplication.objects.select_related('employee')
                                                               .filter(user=logged_in_user, approved=None))
    
    context['vacation_apps_list'] = vacation_apps
    context['absence_apps_list'] = absence_apps
    context['repeat_unav_apps_list'] = repeat_unav_apps

    return HttpResponse(template.render(context, request))
    
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")  
def approve_vacation_app(request):  
    """Approve vacation application."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = PkForm(request.POST)
        if form.is_valid():
            pk = form.cleaned_data['pk']
            vacation_app = (VacationApplication.objects.select_related('employee')
                                                       .get(user=logged_in_user, pk=pk))
            vacation_app.approved = True
            vacation_app.save()
            
            vacation = Vacation(user=logged_in_user,
                                start_datetime=vacation_app.start_datetime,
                                end_datetime=vacation_app.end_datetime,
                                employee=vacation_app.employee)
            vacation.save()
            
            # Inform employee via email and text
            msg = "Your vacation application for %s to %s has been approved." % (vacation.start_datetime, vacation.end_datetime)
            notify_employee_with_msg(vacation_app.employee, msg)
            
            data = {'pk': pk}
            json_data = json.dumps(data)
            return JsonResponse(json_data, safe=False)
        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)
    
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")  
def disapprove_vacation_app(request):  
    """Approve vacation application."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = PkForm(request.POST)
        if form.is_valid():
            pk = form.cleaned_data['pk']
            vacation_app = (VacationApplication.objects.select_related('employee')
                                                       .get(user=logged_in_user, pk=pk))
            vacation_app.approved = False
            vacation_app.save()
            
            data = {'pk': pk}
            json_data = json.dumps(data)
            return JsonResponse(json_data, safe=False)
        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)
    

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
