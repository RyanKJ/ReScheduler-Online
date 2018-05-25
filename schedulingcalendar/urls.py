from django.conf.urls import url

from views import *

app_name = 'schedulingcalendar'
urlpatterns = [
    url(r'^$', front_or_cal_page, name='front_or_cal_page'),
    url(r'^front/$', front_page, name='front_page'),
    url(r'^about/$', about_page, name='about_page'),
    url(r'^contact/$', contact_page, name='contact_page'),
    url(r'^login_success/$', login_success, name='login_success'),
    url(r'^register/$', register, name='register'),
    url(r'^account_activation_sent/$', account_activation_sent, name='account_activation_sent'),
    url(r'^account_activation_success/$', account_activation_success, name='account_activation_success'),
    url(r'^activate/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$', activate, name='activate'),
    url(r'^calendar/$', calendar_page, name='calendar_page'),
    url(r'^calendar/add_schedule$', add_schedule, name='add_schedule'),
    url(r'^calendar/get_schedules$', get_schedules, name='get_schedules'),
    url(r'^calendar/get_schedule_info$', get_schedule_info, name='get_schedule_info'),
    url(r'^calendar/get_proto_schedule_info$', get_proto_schedule_info, name='get_proto_schedule_info'),
    url(r'^calendar/add_employee_to_schedule$', add_employee_to_schedule, name='add_employee_to_schedule'),
    url(r'^calendar/remove_schedule$', remove_schedule, name='remove_schedule'),
    url(r'^calendar/edit_schedule$', edit_schedule, name='edit_schedule'),
    url(r'^calendar/copy_schedules$', copy_schedules, name='copy_schedules'),
    url(r'^calendar/remove_conflict_copy_schedules$', remove_conflict_copy_schedules, name='remove_conflict_copy_schedules'),
    url(r'^calendar/push_changes_live$', push_changes_live, name='push_changes_live'),
    url(r'^calendar/update_view_rights$', update_view_rights, name='update_view_rights'),
    url(r'^calendar/view_live_schedules$', view_live_schedules, name='view_live_schedules'),
    url(r'^calendar/get_live_schedules$', get_live_schedules, name='get_live_schedules'),
    url(r'^calendar/employee_get_live_schedules$', employee_get_live_schedules, name='employee_get_live_schedules'),
    url(r'^calendar/add_edit_day_note_header$', add_edit_day_note_header, name='add_edit_day_note_header'),
    url(r'^calendar/add_edit_day_note_body$', add_edit_day_note_body, name='add_edit_day_note_body'),
    url(r'^calendar/edit_schedule_note$', edit_schedule_note, name='edit_schedule_note'),
    url(r'^employees/$', EmployeeListView.as_view(), name='employee_list'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/info/$', EmployeeUpdateView.as_view(), name='employee_info'),
    url(r'^employees/employee_create$', EmployeeCreateView.as_view(), name='employee_create'),
    url(r'^employees/(?P<pk>[0-9]+)/employee_delete$', EmployeeDeleteView.as_view(), name='employee_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/employee_user_pw/(?P<employee_user_pk>[0-9]+)$', change_employee_pw_as_manager, name='employee_user_pw_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/employee_username/(?P<employee_user_pk>[0-9]+)$', EmployeeUsernameUpdateView.as_view(), name='employee_username_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/employee_user_delete/(?P<pk>[0-9]+)$', EmployeeUserDeleteView.as_view(), name='employee_user_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/employee_user_create$', EmployeeUserCreateView.as_view(), name='employee_user_create'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/vacation/(?P<vacation_pk>[0-9]+)$', VacationUpdateView.as_view(), name='vacation_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/vacation_delete/(?P<pk>[0-9]+)$', VacationDeleteView.as_view(), name='vacation_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/vacation_create$', VacationCreateView.as_view(), name='vacation_create'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/absent/(?P<absent_pk>[0-9]+)$', AbsentUpdateView.as_view(), name='absent_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/absent_delete/(?P<pk>[0-9]+)$', AbsentDeleteView.as_view(), name='absent_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/absent_create$', AbsentCreateView.as_view(), name='absent_create'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/repeat_unavailable/(?P<repeat_unav_pk>[0-9]+)$', RepeatUnavailableUpdateView.as_view(), name='repeat_unav_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/repeat_unavailable_delete/(?P<pk>[0-9]+)$', RepeatUnavailableDeleteView.as_view(), name='repeat_unav_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/repeat_unavailable_create$', RepeatUnavailableCreateView.as_view(), name='repeat_unav_create'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/desired_time/(?P<desired_time_pk>[0-9]+)$', DesiredTimeUpdateView.as_view(), name='desired_time_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/desired_time_delete/(?P<pk>[0-9]+)$', DesiredTimeDeleteView.as_view(), name='desired_time_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/desired_time_create$', DesiredTimeCreateView.as_view(), name='desired_time_create'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/department_membership/(?P<dep_mem_pk>[0-9]+)$', DepartmentMembershipUpdateView.as_view(), name='dep_mem_update'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/department_membership_delete/(?P<pk>[0-9]+)$', DepartmentMembershipDeleteView.as_view(), name='dep_mem_delete'),
    url(r'^employees/(?P<employee_pk>[0-9]+)/department_membership_create$', DepartmentMembershipCreateView.as_view(), name='dep_mem_create'),
    url(r'^departments/$', DepartmentListView.as_view(), name='department_list'),
    url(r'^departments/department_create$', DepartmentCreateView.as_view(), name='department_create'),
    url(r'^departments/(?P<department_pk>[0-9]+)/department_update$', DepartmentUpdateView.as_view(), name='department_update'),
    url(r'^departments/(?P<pk>[0-9]+)/department_delete$', DepartmentDeleteView.as_view(), name='department_delete'),
    url(r'^monthly_revenue/$', MonthlyRevenueListView.as_view(), name='monthly_revenue_list'),
    url(r'^monthly_revenue/monthly_revenue_create$', MonthlyRevenueCreateView.as_view(), name='monthly_revenue_create'),
    url(r'^monthly_revenue/(?P<monthly_rev_pk>[0-9]+)/monthly_revenue_update$', MonthlyRevenueUpdateView.as_view(), name='monthly_revenue_update'),
    url(r'^monthly_revenue/(?P<pk>[0-9]+)/monthly_revenue_delete$', MonthlyRevenueDeleteView.as_view(), name='monthly_revenue_delete'),
    url(r'^business_settings$', BusinessDataUpdateView.as_view(), name='business_update'),
    url(r'^calendar_display_settings$', CalendarDisplayUpdateView.as_view(), name='calendar_display_settings'),
    url(r'^live_calendar/$', employee_calendar_page, name='employee_calendar_page'),
    url(r'^live_calendar/create_schedule_swap_petition$', create_schedule_swap_petition, name='create_schedule_swap_petition'),
    url(r'^pending_approvals/$', pending_approvals_page, name='pending_approvals'),
    url(r'^pending_approvals/schedule_swap_disapproval$', schedule_swap_disapproval, name='schedule_swap_disapproval'),
    url(r'^my_profile/$', EmployeeUpdateProfileSettings.as_view(), name='employee_profile_settings'),
    url(r'^my_availability/$', employee_availability, name='employee_availability'),
]