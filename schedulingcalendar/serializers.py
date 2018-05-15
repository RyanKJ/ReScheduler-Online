from django.forms.models import model_to_dict
from django.http import HttpResponse



def get_tro_dates_to_dict(tro_dates):
    """Convert tro_dates into a dict ready for json serialization."""
    vacations = tro_dates['vacations']
    unavailabilities = tro_dates['unavailabilities']
    
    vacations_as_dicts = []
    for v in vacations:
        vacation_dict = model_to_dict(v)
        vacations_as_dicts.append(vacation_dict)
        
    unavailabilities_as_dicts = []
    for u in unavailabilities:
        unavailabilities_dict = model_to_dict(u)
        unavailabilities_as_dicts.append(unavailabilities_dict)
    
    return {'vacations': vacations_as_dicts, 
            'unavailabilities': unavailabilities_as_dicts}
                          
                          
def eligable_list_to_dict(eligable_list):
    """Convert eligable_list into a dict ready for json serialization.
    
    Args:
        eligable_list: list of sorted eligables with an availability dict and
        a sorting score.
    Returns:
        The eligible list formatted into dicts to be serialized by json.
    """
    
    eligable_serialized_list = []
    
    for e in eligable_list['eligables']:
        eligable_serialized = {}
        eligable_serialized_list.append(eligable_serialized)
        
        # Serialize the employee model
        employee_serialized = model_to_dict(e['employee'])
        eligable_serialized['employee'] = employee_serialized
        # Serialize the availability dict
        avail_serialized = _availability_to_dict(e['availability'])
        eligable_serialized['availability'] = avail_serialized
        
    # Serialize the corresponding schedule
    serialized_schedule = model_to_dict(eligable_list['schedule'])
    
    data = {'schedule': serialized_schedule, 
            'eligable_list': eligable_serialized_list}
            
    return data
    
    
def _availability_to_dict(availability):
    """Convert availability into a dict ready for json serialization.
    
    Args:
        availability: list containing django querysets and other information
        compiled by the get_availability function.
    Returns:
        Availability formatted into dicts to be serialized by json.
    """
    
    MODEL_AVAILABILITIES = ('(S)', '(V)', '(A)', '(U)', 'Desired Times')
    avail_serialized = {}
    
    for key in MODEL_AVAILABILITIES:
        serialized_conflicts = []
        for conflict in availability[key]:
            serial_conf = model_to_dict(conflict)
            serialized_conflicts.append(serial_conf)
            
        avail_serialized[key] = serialized_conflicts
            
    avail_serialized['(O)'] = availability['(O)']
    avail_serialized['Hours Scheduled'] = availability['Hours Scheduled']
    avail_serialized['curr_hours'] =availability['curr_hours']
    
    return avail_serialized
    
    
def get_json_err_response(msg):
    """Create error json response with given error message."""
    response = HttpResponse(json.dumps({'err': msg}), 
        content_type='application/json')
    response.status_code = 400
    return response
      
    
def date_handler(obj):
    """Add converting instructions to JSON parser for datetime objects. 
    
    Written by Anthony Hatchkins: 
    http://stackoverflow.com/questions/23285558/datetime-date2014-4-25-is-not-json-serializable-in-django
    """
    
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError     