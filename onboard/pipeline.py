from django.shortcuts import redirect
from frontend.models import ExperimentMember, ExperimentTypes
from onboard.models import ProlificId
from random import randint
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from django.conf import settings
from smtplib import SMTPException

CURRENT_EXPERIMENT = ExperimentTypes.NEWS
AUTO_EMAILS_ENABLED = False

"""
is_login_attempt_valid:
This function will check if a login attempt is valid. A valid login attempt is defined as either a new account
signing in that has the informed_consent_confirmed flag set to be true, or a returning user (non-new account).
"""
def is_login_attempt_valid(request, **kwargs):
    user_exists = User.objects.filter(username=kwargs['details']['username']).first()
    member_exists = ExperimentMember.objects.filter(social_auth=user_exists, experiment_type=CURRENT_EXPERIMENT).exists()
    if not member_exists and not request.session.get('new_user_informed_consent', False):
        request.session['LOGIN_ERROR'] = f"Error: No matching account found for {kwargs['details']['username']}. Please sign up to create an account."
        return redirect('frontend:start')
    else:
        return kwargs

"""
link_new_account:
Given a new user, this function will link their social auth account to a new ExperimentMember object.
"""
def link_new_account(request, **kwargs):
    experiment_type_int = CURRENT_EXPERIMENT
    user_exists = User.objects.filter(username=kwargs['details']['username']).first()
    member_exists = ExperimentMember.objects.filter(social_auth=user_exists, experiment_type=experiment_type_int).exists()
    if not member_exists and request.session.get('new_user_informed_consent', False) and request.session.get('new_user_prolific_id', False):
        # Create new ExperimentMember object.
        new_user = ExperimentMember(social_auth=kwargs['user'], contact_email=kwargs['details']['email'], experiment_type=experiment_type_int)
        new_user.save()

        prolific_id = ProlificId(prolific_id=request.session['new_user_prolific_id'], user_id=new_user)
        prolific_id.save()

        if AUTO_EMAILS_ENABLED:
            try:
                html_content = render_to_string('onboard/signup_email_template.html', {'user_name': kwargs['details']['first_name'], 'compensation_amount': 15})
                text_content = strip_tags(html_content)
                email = EmailMultiAlternatives(
                    f"Thanks for Signing Up, {kwargs['details']['first_name']}!", text_content, settings.EMAIL_HOST_USER, [kwargs['details']['email']],
                )
                email.attach_alternative(html_content, 'text/html')
                email.send()
                print('Waitlist Email sent!')
            except SMTPException as exception:
                print("Couldn't send email due to smt exception:", exception)
            except Exception as exception:
                print("Couldn't send email:", exception)

        # Delete session object information.
        del request.session['new_user_informed_consent']
        del request.session['new_user_prolific_id']
    return kwargs
