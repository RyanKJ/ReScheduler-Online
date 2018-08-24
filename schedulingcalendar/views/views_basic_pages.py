from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template import loader
from ..models import (Department, DepartmentMembership, Employee,
                      BusinessData, LiveCalendar, DayNoteHeader, DayNoteBody)
from ..forms import (CalendarForm, LiveCalendarForm, LiveCalendarManagerForm,
                     ViewLiveCalendarForm, SetStateLiveCalForm, AddScheduleForm,
                     DayNoteHeaderForm, DayNoteBodyForm, ScheduleNoteForm,
                     SignUpForm, UserSetupForm)
from datetime import datetime, date



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


def about_page(request):
    """Display the about page for the website."""
    template = loader.get_template('schedulingcalendar/about.html')
    context = {}

    return HttpResponse(template.render(context, request))


def contact_page(request):
    """Display the contact page for the website."""
    template = loader.get_template('schedulingcalendar/contact.html')
    context = {}

    return HttpResponse(template.render(context, request))
    
    
def help_page(request):
    """Display the help page for the website."""
    template = loader.get_template('schedulingcalendar/help.html')
    context = {}

    return HttpResponse(template.render(context, request))


def manager_check(user):
    """Checks if user is a manager user or not."""
    return user.groups.filter(name="Managers").exists()


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

    set_live_cal_form = SetStateLiveCalForm(logged_in_user, department, initial={'all_employee_view': True})


    context = {'calendar_form': calendar_form,
               'add_sch_form': add_schedule_form,
               'time_interval': business_data.time_picker_interval,
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
    """Display the live calendar page for an employee user."""
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
def new_manager_user_setup(request):
    """Display the quick setup for new manager users form."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = UserSetupForm(request.POST)
        if form.is_valid():
            company_name = form.cleaned_data['company_name']
            department_name = form.cleaned_data['department_name']
            e1_first_name = form.cleaned_data['employee_1_first_name']
            e1_last_name = form.cleaned_data['employee_1_last_name']
            e2_first_name = form.cleaned_data['employee_2_first_name']
            e2_last_name = form.cleaned_data['employee_2_last_name']
            e3_first_name = form.cleaned_data['employee_3_first_name']
            e3_last_name = form.cleaned_data['employee_3_last_name']
            
            # Save company name
            business_settings = BusinessData.objects.get(user=logged_in_user)
            business_settings.company_name = company_name
            business_settings.save()
            
            # Create department
            new_dep = Department(user=logged_in_user, name=department_name)
            new_dep.save()
            
            # Create employees
            employee_1 = Employee(user=logged_in_user, first_name=e1_first_name, last_name=e1_last_name)
            employee_2 = Employee(user=logged_in_user, first_name=e2_first_name, last_name=e2_last_name)
            employee_3 = Employee(user=logged_in_user, first_name=e3_first_name, last_name=e3_last_name)
            employee_1.save()
            employee_2.save()
            employee_3.save()
            
            # Assign employees to department
            employee_1_dep_mem = DepartmentMembership(user=logged_in_user, employee=employee_1, department=new_dep)
            employee_2_dep_mem = DepartmentMembership(user=logged_in_user, employee=employee_2, department=new_dep)
            employee_3_dep_mem = DepartmentMembership(user=logged_in_user, employee=employee_3, department=new_dep)
            employee_1_dep_mem.save()
            employee_2_dep_mem.save()
            employee_3_dep_mem.save()
            
            return redirect('/calendar/')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = UserSetupForm()
    return render(request, 'schedulingcalendar/newUserSetup.html', { 'form': form })

