from django.conf.urls import url

from . import views

app_name = 'schedulingcalendar'
urlpatterns = [
    url(r'^$', views.front_page, name='front_page'),
    url(r'^calendar/$', views.calendar_page, name='calendar_page'),
    url(r'^calendar/add_schedule$', views.add_schedule, name='add_schedule'),
    url(r'^calendar/get_schedules$', views.get_schedules, name='get_schedules'),
    url(r'^calendar/get_schedule_info$', views.get_schedule_info, name='get_schedule_info'),
    url(r'^calendar/add_employee_to_schedule$', views.add_employee_to_schedule, name='add_employee_to_schedule'),
    url(r'^calendar/remove_schedule$', views.remove_schedule, name='remove_schedule'),
    url(r'^employees/$', views.EmployeeListView.as_view(), name='employee_list'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/info/$', views.EmployeeUpdateView.as_view(), name='employee_info'),
    url(r'^employees/employee_create$', views.EmployeeCreateView.as_view(), name='employee_create'),
    url(r'^employees/(?P<pk>[0-9]+)/employee_delete$', views.EmployeeDeleteView.as_view(), name='employee_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/vacations/$', views.VacationListView.as_view(), name='employee_vacations'),
    
]