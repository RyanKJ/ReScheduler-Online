from django.core import serializers
from django.shortcuts import render, get_list_or_404
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.views.generic import ListView, FormView, CreateView, UpdateView, DeleteView
from .models import Schedule, Department, Employee, Vacation
from .business_logic import get_eligables, eligable_list_to_dict, date_handler
from .forms import CalendarForm, AddScheduleForm
from .custom_mixins import AjaxFormResponseMixin
from datetime import datetime, date, timedelta
from itertools import chain
import json



def front_page(request):
    """Display the front page for the website."""
    template = loader.get_template('schedulingcalendar/front.html')
    context = {}

    return HttpResponse(template.render(context, request))


@login_required
def calendar_page(request):
    """Display the schedule editing page for a managing user."""
    logged_in_user = request.user
    
    calendar_form = CalendarForm(logged_in_user)
    add_schedule_form = AddScheduleForm()
    template = loader.get_template('schedulingcalendar/calendar.html')
    context = {'calendar_form': calendar_form, 'add_sch_form': add_schedule_form}

    return HttpResponse(template.render(context, request))
    
    
@login_required
def employee_list(request):
    """Display the employee editing page for a managing user."""
    logged_in_user = request.user
    
    # TODO: Get all employees for user and load into page?
    employee_form = EmployeeForm()
    employee_list = Employee.objects.filter(user=logged_in_user)
    
    template = loader.get_template('schedulingcalendar/employeeList.html')
    context = {'employee_form': employee_form, 'employee_list': employee_list}

    return HttpResponse(template.render(context, request))


@login_required
def get_schedules(request):
    """Display schedules for a given user, month, year, and department."""
    logged_in_user = request.user
    print "******** get_schedules is ajax request?: ", request.is_ajax()
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
                
            # Combine all appropriate data into dict for serialization
            combined_dict = {'date': cal_date.isoformat(), 
                             'department': department_id,
                             'schedules': schedules_as_dicts,
                             'employees': employees_as_dicts}
            combined_json = json.dumps(combined_dict, default=date_handler)
            
            return JsonResponse(combined_json, safe=False)
    
    else:
      # err_msg = "Year, Month, or Department was not selected."
      # TODO: Send back Unsuccessful Response
      pass

    
@login_required
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
def get_schedule_info(request):
    """Returns information for schedule such as eligable employees."""
    logged_in_user = request.user
    print "******** get_schedule_info is ajax request?: ", request.is_ajax()
    schedule_pk = request.GET['pk']
    schedule = Schedule.objects.get(user=logged_in_user, pk=schedule_pk)
    
    eligable_list = get_eligables(schedule)
    eligable_dict_list = eligable_list_to_dict(eligable_list)
    json_data = json.dumps(eligable_dict_list, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    

@login_required
def add_employee_to_schedule(request):
    """Assign employee to schedule."""
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
    """Remove schedule from the database."""
    logged_in_user = request.user
    schedule_pk = request.POST['schedule_pk']
    schedule = Schedule.objects.get(user=logged_in_user, pk=schedule_pk)
    schedule.delete()
    
    json_info = json.dumps({'schedule_pk': schedule_pk}, default=date_handler)
    return JsonResponse(json_info, safe=False)
    
        
@method_decorator(login_required, name='dispatch')
class EmployeeListView(ListView):
    model = Employee
    template_name = 'schedulingcalendar/employeeList.html'
    context_object_name = 'employee_list'
        
    def get_queryset(self):
        return Employee.objects.filter(user=self.request.user)
        
 
@method_decorator(login_required, name='dispatch') 
class EmployeeUpdateView(UpdateView):
    template_name = 'schedulingcalendar/employeeInfo.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    fields = ['first_name', 'last_name', 'employee_id', 'email',
              'wage', 'desired_hours', 'monthly_medical',
              'workmans_comp', 'social_security']
    
    def get(self, request, **kwargs):
        self.object = Employee.objects.get(pk=self.kwargs['employee_pk'], user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

        
    def get_object(self, queryset=None):
        obj = Employee.objects.get(pk=self.kwargs['employee_pk'], user=self.request.user)
        return obj
        
        
@method_decorator(login_required, name='dispatch') 
class EmployeeCreateView(CreateView):
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
class EmployeeDeleteView(DeleteView):
    template_name = 'schedulingcalendar/employeeDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = Employee
    
    
    