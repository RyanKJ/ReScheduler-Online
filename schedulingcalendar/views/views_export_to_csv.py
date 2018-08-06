from django.template import loader
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .views_basic_pages import manager_check
from ..forms import ExportToCSVForm
from ..models import Schedule, Department, Employee, BusinessData
from ..serializers import get_json_err_response
from datetime import datetime, date, time
import csv


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")  
def export_to_csv_page(request):
    """Display the csv exporting page for a managing user."""
    logged_in_user = request.user
    
    template = loader.get_template('schedulingcalendar/exportToCSV.html')
    context = {}
    export_to_csv_form = ExportToCSVForm()
    context['form'] = export_to_csv_form

    return HttpResponse(template.render(context, request))
    
    
@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")  
def export_schedules_to_csv(request):
    """Generate CSV file of all schedules in date range."""
    logged_in_user = request.user
    if request.method == 'GET':
        form = ExportToCSVForm(request.GET)
        if form.is_valid():
            date_start = form.cleaned_data['month_year_start']
            date_end = form.cleaned_data['month_year_end']
            
            # Create timezone aware datetimes from date ranges
            now = timezone.now()
            dt_start = datetime.combine(date_start, now.time())
            dt_end = datetime.combine(date_end, now.time())
            
            schedules = (Schedule.objects.select_related('department', 'employee')
                                         .filter(user=logged_in_user, start_datetime__range=(dt_start, dt_end))
                                         .order_by('department', 'employee', 'start_datetime', 'end_datetime'))
            
            # Create CSV file
            business_data = BusinessData.objects.get(user=logged_in_user)
            company_name = business_data.company_name.replace(" ", "")
            start_str = date_start.strftime("%Y-%m")
            end_str = date_end.strftime("%Y-%m")
            file_name = company_name + "-" + start_str + "-to-" + end_str
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename='+file_name+'.csv'

            writer = csv.writer(response)
            writer.writerow(['Department', 'Employee', 'Start Time', 'End Time', 
                             'Start time was hidden?', 'End time was hidden?',
                             'Note'])
                             
            for s in schedules:
                writer.writerow([s.department, s.employee, 
                                 s.start_datetime.isoformat(), s.end_datetime.isoformat(), 
                                 s.hide_start_time, s.hide_end_time, s.schedule_note])

            return response
        else:
            msg = 'Invalid form data'
            return get_json_err_response(msg)
    else:
        msg = 'HTTP request needs to be GET. Got: ' + request.method
        return get_json_err_response(msg)