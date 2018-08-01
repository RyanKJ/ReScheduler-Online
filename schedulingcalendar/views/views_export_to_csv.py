from django.template import loader
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from .views_basic_pages import manager_check
from ..forms import ExportToCSVForm


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
    """
    logged_in_user = request.user
    if request.method == 'GET':
        form = ExportToCSVForm(request.GET)
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
        """