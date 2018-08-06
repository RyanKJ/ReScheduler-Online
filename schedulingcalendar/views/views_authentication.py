from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template import loader
from django.core.mail import send_mail
from ..tokens import account_activation_token, account_delete_token
from ..models import Department, DepartmentMembership, Employee, BusinessData
from ..forms import SignUpForm, DeleteAccountForm, DeleteAccountFeedbackForm
from datetime import datetime, date



def manager_check(user):
    """Checks if user is a manager user or not."""
    return user.groups.filter(name="Managers").exists()


@login_required
def account_settings(request):
    """Page to edit account such as changing password."""
    template = loader.get_template('registration/account_settings.html')
    context = {}

    return HttpResponse(template.render(context, request))


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
        user.userprofile.email_confirmed = True
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


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def change_password(request):
    """Change password of manager user"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('/account_settings/')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'registration/password_change.html', {'form': form})


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def delete_account(request):
    """Send email confirmation asking user to confirm desire to delete account."""
    logged_in_user = request.user
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            delete_str = form.cleaned_data['delete_str']
            if delete_str == "DELETEMYACCOUNT":
                current_site = get_current_site(request)
                subject = 'Delete your Schedule Hours account'
                message = loader.render_to_string('registration/account_delete_email.html', {
                    'user': logged_in_user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(logged_in_user.pk)),
                    'token': account_delete_token.make_token(logged_in_user),
                })
                logged_in_user.email_user(subject, message)
                return redirect("/account_delete_sent/")
            else:
                form = DeleteAccountForm()
    else:
        form = DeleteAccountForm()
    return render(request, 'registration/delete_account.html', {'form': form})


@login_required
@user_passes_test(manager_check, login_url="/live_calendar/")
def delete_confirm(request, uidb64, token):
    """Delete user if user's token matches url token."""
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_delete_token.check_token(user, token):
        user.delete()
        form = DeleteAccountFeedbackForm()
        return render(request, 'registration/delete_account_feedback.html', {'form': form})
    else:
        return render(request, 'registration/account_delete_invalid.html')


def account_delete_sent(request):
    """Display the confirmation email sent page for user account termination."""
    template = loader.get_template('registration/account_delete_sent.html')
    context = {}

    return HttpResponse(template.render(context, request))


def account_delete_feedback_send(request):
    """Submit feedback to email."""
    if request.method == 'POST':
        form = DeleteAccountFeedbackForm(request.POST)
        if form.is_valid():
            feedback_text = form.cleaned_data['feedback_text']
            send_mail('Feedback', feedback_text, 'info@schedulehours.com', ['info@schedulehours.com'])
            return render(request, 'registration/feedback_thankyou.html')
        else:
            return redirect('/front/')
    else:
        return redirect('/front/')
        
        
def change_email(request):
    """Send authorization email to change email of user account."""
    if request.method == 'POST':
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']
            new_email_repeat = form.cleaned_data['new_email']
            if new_email == new_email_repeat:
                current_site = get_current_site(request)
                subject = 'Change the email associated with your Schedule Hours account'
                message = loader.render_to_string('registration/account_email_change.html', {
                          'new_email': new_email,
                          'user': logged_in_user,
                          'domain': current_site.domain,
                          'uid': urlsafe_base64_encode(force_bytes(logged_in_user.pk)),
                          'token': account_email_change_token.make_token(logged_in_user),
                })
                logged_in_user.email_user(subject, message)
        
                return redirect("/account_email_change_sent/")
            else:
              form = ChangeEmailForm()
        else:
            form = ChangeEmailForm()
    return render(request, 'registration/change_email.html')
    
    
def email_change_confirm(request):
    """Change email of user if user's token matches url token."""
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_delete_token.check_token(user, token):
        # Change profile email
        user.email = new_email
        user.save()
        return render(request, 'registration/delete_account_feedback.html')
    else:
        return render(request, 'registration/account_delete_invalid.html')
    
    
    
    
    
    
