from .custom_shortcuts import render_to_json_response
from django.contrib.auth.mixins import UserPassesTestMixin

# a mixin to add AJAX support to a form
# must be used with an object-based FormView (e.g. CreateView)
class AjaxFormResponseMixin(object):

    def form_invalid(self, form):
        return render_to_json_response(form.errors, status=400)
        

    def form_valid(self, form):

        # save
        self.object = form.save()

        # initialize an empty context
        context = {}

        # return the context as json
        return render_to_json_response(self.get_context_data(context))
        
        
class UserIsManagerMixin(UserPassesTestMixin):
    """Tests if user is manager for manager based views."""
    login_url = "/live_calendar/"
    
    def test_func(self):
        """Check if user is a manager user."""
        return self.request.user.groups.filter(name="Managers").exists()