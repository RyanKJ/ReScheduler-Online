from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.http import urlsafe_base64_decode
from django.template import loader
from django.core.mail import send_mail
from ..tokens import account_activation_token
from ..models import Department, DepartmentMembership, Employee, BusinessData     
from datetime import datetime, date
    
    

def manager_check(user):
    """Checks if user is a manager user or not."""
    return user.groups.filter(name="Managers").exists()
    
 
@login_required 
def login_success(request):
    """Redirect user based on if they are manager or employee."""
    if manager_check(request.user):
        return redirect("/calendar/") # Manager calendar
    else:
        return redirect("/live_calendar/") # Employee calendar

    
def register(request):
    """User registration that sends out an email confirmation with token."""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            
            current_site = get_current_site(request)
            subject = 'Activate Your Schedule Hours Business Account'
            message = loader.render_to_string('registration/account_activation_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            user.email_user(subject, message)
            return redirect("/account_activation_sent/")
    else:
        form = SignUpForm()
    return render(request, 'registration/signUp.html', {'form': form})
    
    
def activate(request, uidb64, token):
    """Activate user if user's token matches url token."""
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.managerprofile.email_confirmed = True
        user.save()
        
        # Add user to manager group for permissions
        manager_user_group = Group.objects.get(name="Managers")
        user.groups.add(manager_user_group)
        
        # TODO: Should redirect to a page to create company/departments/3 employees
        # Create business logic for user
        business_data = BusinessData(user=user)
        business_data.save()
        department = Department(user=user, name="Main")
        department.save()

        login(request, user)
        return redirect('/calendar/')
    elif user is not None:
        return redirect("/login/")
    else:
        return render(request, 'registration/account_activation_invalid.html')
    
    
def account_activation_sent(request):
    """Display the confirmation email sent page for user registration."""
    template = loader.get_template('registration/account_activation_sent.html')
    context = {}

    return HttpResponse(template.render(context, request))
    
    
def account_activation_success(request):
    """Display the account registration success page."""
    template = loader.get_template('registration/account_activation_success.html')
    context = {}

    return HttpResponse(template.render(context, request))
   