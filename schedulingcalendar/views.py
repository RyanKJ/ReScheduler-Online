from django.core import serializers
from django.shortcuts import render, get_list_or_404
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.views.generic import ListView, FormView, CreateView, UpdateView, DeleteView
from .models import (Schedule, Department, DepartmentMembership, Employee, 
                     Vacation, RepeatUnavailability, DesiredTime, MonthlyRevenue)
from .business_logic import (get_eligables, eligable_list_to_dict,  
                             date_handler, schedule_cost, all_calendar_costs, 
                             get_avg_monthly_revenue)
from .forms import CalendarForm, AddScheduleForm, VacationForm
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
                
            # Get calendar costs to display to user
            calendar_costs = all_calendar_costs(logged_in_user, month, year)
            avg_monthly_revenue = get_avg_monthly_revenue(logged_in_user, month)
                
            # Combine all appropriate data into dict for serialization
            combined_dict = {'date': cal_date.isoformat(), 
                             'department': department_id,
                             'schedules': schedules_as_dicts,
                             'employees': employees_as_dicts,
                             'all_calendar_costs': calendar_costs,
                             'avg_monthly_revenue': avg_monthly_revenue}
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
    # Get schedule and its cost with old employee
    schedule = (Schedule.objects.select_related('department', 'employee')
                                .get(user=logged_in_user, pk=schedule_pk))
    old_cost = schedule_cost(schedule)
    
    # Get new employee, assign to schedule, then get new cost of schedule
    new_employee = Employee.objects.get(user=logged_in_user, pk=employee_pk)
    schedule.employee = new_employee
    schedule.save(update_fields=['employee'])
    new_cost = schedule_cost(schedule)
    
    # Process information for json dump
    cost_delta = {'id': schedule.department.id, 'cost': new_cost - old_cost}
    schedule_dict = model_to_dict(schedule)
    employee_dict = model_to_dict(new_employee)
    data = {'schedule': schedule_dict, 'employee': employee_dict, 
            'cost_delta': cost_delta}
    json_data = json.dumps(data, default=date_handler)
    
    return JsonResponse(json_data, safe=False)
    

@login_required
def remove_schedule(request):
    """Remove schedule from the database."""
    logged_in_user = request.user
    schedule_pk = request.POST['schedule_pk']
    schedule = (Schedule.objects.select_related('department', 'employee')
                                .get(user=logged_in_user, pk=schedule_pk))
    
    sch_cost = 0 - schedule_cost(schedule)
    cost_delta = {'id': schedule.department.id, 'cost': sch_cost}
    schedule.delete()
    
    json_info = json.dumps({'schedule_pk': schedule_pk, 'cost_delta': cost_delta},
                            default=date_handler)
    return JsonResponse(json_info, safe=False)
    
        
@method_decorator(login_required, name='dispatch')
class EmployeeListView(ListView):
    """Display an alphabetical list of all employees for a managing user."""
    model = Employee
    template_name = 'schedulingcalendar/employeeList.html'
    context_object_name = 'employee_list'
        
    def get_queryset(self):
        return (Employee.objects.filter(user=self.request.user)
                                .order_by('first_name', 'last_name'))
        
 
@method_decorator(login_required, name='dispatch') 
class EmployeeUpdateView(UpdateView):
    """Display employee form and associated lists, ie vacations of employee."""
    template_name = 'schedulingcalendar/employeeInfo.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    fields = ['first_name', 'last_name', 'employee_id', 'email',
              'wage', 'desired_hours', 'monthly_medical',
              'workmans_comp', 'social_security']
    
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
        context = super(EmployeeUpdateView, self).get_context_data(**kwargs)
        context['department_mem_list'] = (DepartmentMembership.objects.filter(employee=self.kwargs['employee_pk'],
                                                                              user=self.request.user)
                                                                      .order_by('priority', 'seniority'))        
        context['vacation_list'] = (Vacation.objects.filter(employee=self.kwargs['employee_pk'],
                                                           user=self.request.user)
                                                    .order_by('start_datetime', 'end_datetime'))
        context['repeating_unavailable_list'] = (RepeatUnavailability.objects.filter(employee=self.kwargs['employee_pk'],
                                                                                    user=self.request.user)
                                                                     .order_by('weekday', 'start_time', 'end_time'))
        context['desired_time_list'] = (DesiredTime.objects.filter(employee=self.kwargs['employee_pk'],
                                                                  user=self.request.user)       
                                                           .order_by('weekday', 'start_time', 'end_time'))                                                                  

        return context
        
        
@method_decorator(login_required, name='dispatch') 
class EmployeeCreateView(CreateView):
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
class EmployeeDeleteView(DeleteView):
    """Display a delete form to delete employee object."""
    template_name = 'schedulingcalendar/employeeDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = Employee
    
    
@method_decorator(login_required, name='dispatch')
class VacationUpdateView(UpdateView):
    """Display vacation form to edit vacation object."""
    template_name = 'schedulingcalendar/vacationUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
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
    
   
@method_decorator(login_required, name='dispatch')
class VacationCreateView(CreateView):
    """Display vacation form to create vacation object."""
    template_name = 'schedulingcalendar/vacationCreate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
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
        
        
@method_decorator(login_required, name='dispatch') 
class VacationDeleteView(DeleteView):
    """Display a delete form to delete vacation object."""
    template_name = 'schedulingcalendar/vacationDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = Vacation
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of vacations to context."""
        context = super(VacationDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
@method_decorator(login_required, name='dispatch')
class RepeatUnavailableUpdateView(UpdateView):
    """Display repeat unavailable form to edit unav repeat object."""
    template_name = 'schedulingcalendar/repeatUnavailableUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    fields = ['start_time', 'end_time', 'weekday']
    
    
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
    
   
@method_decorator(login_required, name='dispatch')
class RepeatUnavailableCreateView(CreateView):
    """Display repeat unavailable form to create unav repeat object."""
    template_name = 'schedulingcalendar/repeatUnavailableCreate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = RepeatUnavailability
    fields = ['start_time', 'end_time', 'weekday']
              
              
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
        
        
@method_decorator(login_required, name='dispatch') 
class RepeatUnavailableDeleteView(DeleteView):
    """Display a delete form to delete unavailable repeat object."""
    template_name = 'schedulingcalendar/repeatUnavailableDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = RepeatUnavailability
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of unavailable repeat to context."""
        context = super(RepeatUnavailableDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
@method_decorator(login_required, name='dispatch')
class DesiredTimeUpdateView(UpdateView):
    """Display desired time form to edit object."""
    template_name = 'schedulingcalendar/desiredTimeUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    fields = ['start_time', 'end_time', 'weekday']
    
    
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
    
   
@method_decorator(login_required, name='dispatch')
class DesiredTimeCreateView(CreateView):
    """Display desired time form to create object."""
    template_name = 'schedulingcalendar/desiredTimeCreate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = DesiredTime
    fields = ['start_time', 'end_time', 'weekday']
              
              
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
        
        
@method_decorator(login_required, name='dispatch') 
class DesiredTimeDeleteView(DeleteView):
    """Display a delete form to delete desired time object."""
    template_name = 'schedulingcalendar/desiredTimeDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = DesiredTime
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of desired time to context."""
        context = super(DesiredTimeDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
@method_decorator(login_required, name='dispatch')
class DepartmentMembershipUpdateView(UpdateView):
    """Display department membership form to edit existing object."""
    template_name = 'schedulingcalendar/departmentMembershipUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
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
    
   
@method_decorator(login_required, name='dispatch')
class DepartmentMembershipCreateView(CreateView):
    """Display department membership form to create object."""
    template_name = 'schedulingcalendar/departmentMembershipCreate.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
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
        
        
@method_decorator(login_required, name='dispatch') 
class DepartmentMembershipDeleteView(DeleteView):
    """Display a delete form to delete department membership object."""
    template_name = 'schedulingcalendar/departmentMembershipDelete.html'
    success_url = reverse_lazy('schedulingcalendar:employee_list')
    model = DepartmentMembership
    
    
    def get_context_data(self, **kwargs):
        """Add employee owner of department membership to context."""
        context = super(DepartmentMembershipDeleteView, self).get_context_data(**kwargs)
        context['employee'] = Employee.objects.get(pk=self.kwargs['employee_pk'],
                                                   user=self.request.user)                                               
        return context
        
        
@method_decorator(login_required, name='dispatch')
class DepartmentListView(ListView):
    """Display an alphabetical list of all departments for a managing user."""
    model = Department
    template_name = 'schedulingcalendar/departmentList.html'
    context_object_name = 'department_list'
        
    def get_queryset(self):
        return Department.objects.filter(user=self.request.user).order_by('name')
        
        
@method_decorator(login_required, name='dispatch')
class DepartmentUpdateView(UpdateView):
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
class DepartmentCreateView(CreateView):
    """Display department form to create object."""
    template_name = 'schedulingcalendar/departmentCreate.html'
    success_url = reverse_lazy('schedulingcalendar:department_list')
    model = Department
    fields = ['name']
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(DepartmentCreateView, self).form_valid(form)
        
        
@method_decorator(login_required, name='dispatch') 
class DepartmentDeleteView(DeleteView):
    """Display a delete form to delete department object."""
    template_name = 'schedulingcalendar/departmentDelete.html'
    success_url = reverse_lazy('schedulingcalendar:department_list')
    model = Department
    
    
@method_decorator(login_required, name='dispatch')
class MonthlyRevenueListView(ListView):
    """Display an alphabetical list of all departments for a managing user."""
    model = MonthlyRevenue
    template_name = 'schedulingcalendar/monthlyRevenueList.html'
    context_object_name = 'monthly_revenue_list'
        
    def get_queryset(self):
        return (MonthlyRevenue.objects.filter(user=self.request.user)
                                      .order_by('month_year'))
        
        
@method_decorator(login_required, name='dispatch')
class MonthlyRevenueUpdateView(UpdateView):
    """Display department form to edit existing department object."""
    template_name = 'schedulingcalendar/monthlyRevenueUpdate.html'
    success_url = reverse_lazy('schedulingcalendar:monthly_revenue_list')
    fields = ['monthly_total', 'month_year']
    
    
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
class MonthlyRevenueCreateView(CreateView):
    """Display department form to create object."""
    template_name = 'schedulingcalendar/monthlyRevenueCreate.html'
    success_url = reverse_lazy('schedulingcalendar:monthly_revenue_list')
    model = MonthlyRevenue
    fields = ['monthly_total', 'month_year']
              
              
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(MonthlyRevenueCreateView, self).form_valid(form)
        
        
@method_decorator(login_required, name='dispatch') 
class MonthlyRevenueDeleteView(DeleteView):
    """Display a delete form to delete department object."""
    template_name = 'schedulingcalendar/monthlyRevenueDelete.html'
    success_url = reverse_lazy('schedulingcalendar:monthly_revenue_list')
    model = MonthlyRevenue
        
        

        
    