import json
from django.shortcuts import _get_queryset
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateformat import format
from django.conf import settings


# replacement for django.shortcuts.get_object_or_404()
# allows json to be returned with a 404 error
def get_object_or_json404(klass, *args, **kwargs):

    queryset = _get_queryset(klass)

    try:
        return queryset.get(*args, **kwargs)
        
    except queryset.model.DoesNotExist:
        raise JsonNotFound()


def render_to_json_response(context, **response_kwargs):
    # returns a JSON response, transforming 'context' to make the payload
    response_kwargs['content_type'] = 'application/json'
    return HttpResponse(convert_context_to_json(context), **response_kwargs)


def convert_context_to_json(context):
    # convert the context dictionary into a JSON object
    # note: this is *EXTREMELY* naive; in reality, you'll need
    # to do much more complex handling to ensure that arbitrary
    # objects -- such as Django model instances or querysets
    # -- can be serialized as JSON.
    return json.dumps(context)
    
    
class JsonNotFound(Exception):

    def __init__(self):

        Exception.__init__(self, 'Record not found')
        
        
class ExceptionMiddleware(object):

    def process_exception(self, request, exception):
        if type(exception) == JsonNotFound:
            now = format(timezone.now(), u'U')
            kwargs = {}
            response = {
                'status': '404',
                'message': 'Record not found',
                'timestamp': now,
                'errorcode': settings.API_ERROR_RECORD_NOT_FOUND
            }
            return render_to_json_response(response, status=404, **kwargs)
        
        return None