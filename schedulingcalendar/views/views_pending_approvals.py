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