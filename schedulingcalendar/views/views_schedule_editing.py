from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.template import loader
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.forms.models import model_to_dict
from ..models import (Schedule, Department, DepartmentMembership, Employee,
                     Vacation, RepeatUnavailability, DesiredTime, MonthlyRevenue,
                     Absence, BusinessData, LiveSchedule, LiveCalendar,
                     DayNoteHeader, DayNoteBody)
from ..business_logic import (get_eligibles, all_calendar_hours_and_costs,
                              add_employee_cost_change, remove_schedule_cost_change,
                              create_live_schedules, time_dur_in_hours,
                              edit_schedule_cost_change, calculate_cost_delta,
                              get_start_end_of_weekday, get_availability, get_dates_in_week,
                              set_view_rights, send_employee_notifications,
                              view_right_send_employee_notifications)
from ..forms import (CalendarForm, AddScheduleForm, ProtoScheduleForm,
                    LiveCalendarForm, LiveCalendarManagerForm, ViewLiveCalendarForm,
                    DayNoteHeaderForm, DayNoteBodyForm, ScheduleNoteForm,
                    EditScheduleForm, CopySchedulesForm, SetStateLiveCalForm,
                    SchedulePkForm, AddEmployeeToScheduleForm, RemoveScheduleForm)
from ..serializers import (date_handler, get_json_err_response, _availability_to_dict,
                           eligable_list_to_dict, get_tro_dates_to_dict, _availability_to_dict)
from .views_basic_pages import manager_check
from datetime import datetime, date, time, timedelta
import bisect
import pytz
import json
import copy



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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def get_schedule_info(request):
    """Returns eligible list of employees for given schedule pk."""
    logged_in_user = request.user
    if request.method == 'GET':
        form = SchedulePkForm(request.GET)
        if form.is_valid():
            schedule_pk = form.cleaned_data['schedule_pk']
            schedule = (Schedule.objects.select_related('department', 'employee', 'user')
                                        .get(user=logged_in_user, pk=schedule_pk))

            eligable_list = get_eligibles(logged_in_user, schedule)
            eligable_dict_list = eligable_list_to_dict(eligable_list)
            json_data = json.dumps(eligable_dict_list, default=date_handler)

            return JsonResponse(json_data, safe=False)

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be GET. Got: ' + request.method
        return get_json_err_response(msg)


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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be GET. Got: ' + request.method
        return get_json_err_response(msg)


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def add_employee_to_schedule(request):
    """Assign employee to schedule."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = AddEmployeeToScheduleForm(request.POST)
        if form.is_valid():
            schedule_pk = form.cleaned_data['schedule_pk']
            employee_pk = form.cleaned_data['employee_pk']
            cal_date = form.cleaned_data['cal_date']
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

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def remove_schedule(request):
    """Remove schedule from the database."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = RemoveScheduleForm(request.POST)
        if form.is_valid():
            schedule_pk = form.cleaned_data['schedule_pk']
            cal_date = form.cleaned_data['cal_date']
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

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)



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

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def copy_schedules(request):
    """Copy set of schedules pks with given date."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = CopySchedulesForm(request.POST)
        if form.is_valid():
            is_day_copy = form.cleaned_data['is_day_copy']
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
                if is_day_copy:
                    new_start_dt = sch.start_datetime.replace(year=date.year, month=date.month, day=date.day)
                    new_end_dt = sch.end_datetime.replace(year=date.year, month=date.month, day=date.day)
                else: # Copy week
                    week_dates = get_dates_in_week(date)
                    for day in week_dates:
                        if sch.start_datetime.weekday() == day.weekday():
                            new_start_dt = sch.start_datetime.replace(year=day.year, month=day.month, day=day.day)
                            new_end_dt = sch.end_datetime.replace(year=day.year, month=day.month, day=day.day)
                            break

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

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


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

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def push_changes_live(request):
    """Create a live version of schedules for employee users to query."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = SetStateLiveCalForm(logged_in_user, None, request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            department_pk = form.cleaned_data['department']
            all_employee_view = form.cleaned_data['all_employee_view']
            department_view = form.cleaned_data['department_view']
            employee_view = form.cleaned_data['employee_view']
            notify_by_sms = form.cleaned_data['notify_by_sms']
            notify_by_email = form.cleaned_data['notify_by_email']
            notify_all = form.cleaned_data['notify_all']

            # Get or create live calendar
            department = Department.objects.get(pk=department_pk)
            live_calendar, created = LiveCalendar.objects.get_or_create(user=logged_in_user,
                                                                        date=date,
                                                                        department=department)
            if created:
                live_calendar.all_employee_view = all_employee_view
                live_calendar.save()
                create_live_schedules(logged_in_user, live_calendar)
            else:
                live_calendar.all_employee_view = all_employee_view
                live_calendar.version += 1
                live_calendar.save()
                create_live_schedules(logged_in_user, live_calendar)

            # Set specific view rights
            set_view_rights(logged_in_user, live_calendar, department_view, employee_view)
            view_rights = {'all_employee_view': all_employee_view,
                           'department_view': department_view,
                           'employee_view': employee_view}

            # Send texts and emails with new/changed schedules
            if notify_by_sms or notify_by_email:
                business_data = BusinessData.objects.get(user=logged_in_user)
                send_employee_notifications(logged_in_user, department, date, business_data,
                                            live_calendar, view_rights, notify_all,
                                            notify_by_sms, notify_by_email)


            json_info = json.dumps({'message': 'Successfully pushed calendar live!', 'view_rights': view_rights})
            return JsonResponse(json_info, safe=False)

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def update_view_rights(request):
    """Deactivate or reactivate the live_calendar for given month"""
    logged_in_user = request.user
    if request.method == 'POST':
        form = SetStateLiveCalForm(logged_in_user, None, request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            department_pk = form.cleaned_data['department']
            all_employee_view = form.cleaned_data['all_employee_view']
            department_view = form.cleaned_data['department_view']
            employee_view = form.cleaned_data['employee_view']
            notify_by_sms = form.cleaned_data['notify_by_sms']
            notify_by_email = form.cleaned_data['notify_by_email']

            # Get live calendar and text appropriate employees
            department = Department.objects.get(pk=department_pk)
            live_calendar = LiveCalendar.objects.get(user=logged_in_user,
                                                     date=date,
                                                     department=department)
            view_rights = {'all_employee_view': all_employee_view,
                           'department_view': department_view,
                           'employee_view': employee_view}
            if notify_by_sms or notify_by_email:
                business_data = BusinessData.objects.get(user=logged_in_user)
                view_right_send_employee_notifications(logged_in_user, department, date, business_data,
                                                       live_calendar, copy.deepcopy(view_rights),
                                                       notify_by_sms, notify_by_email)

            live_calendar.all_employee_view = all_employee_view
            live_calendar.save()

            # Set specific view rights
            set_view_rights(logged_in_user, live_calendar, department_view, employee_view)

            json_info = json.dumps({'message': 'Successfully updated view rights', 'view_rights': view_rights})
            return JsonResponse(json_info, safe=False)

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


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
            except:
                message = 'No live calendar currently exists for this month, year, and department.'

            json_info = json.dumps({'message': message})
            return JsonResponse(json_info, safe=False)

        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be GET. Got: ' + request.method
        return get_json_err_response(msg)


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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)


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
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be POST. Got: ' + request.method
        return get_json_err_response(msg)
