from django.shortcuts import render, redirect
from django.views import View
from frontend.models import ExperimentMember
from frontend.forms import IntroSurveyFormNews
from onboard.forms import InformedConsentForm, OnboardForm, DemographicsForm, ExtensionForm
from onboard.models import Demographics, OnboardCode, ProlificId
from onboard.pipeline import CURRENT_EXPERIMENT
import datetime
import re

STUDY_DURATION_DAYS = "14-28"
STUDY_COMPENSATION = "15"

# OnboardView Class extends default class View, adds utility classes
class OnboardView(View):  
    def is_chrome(self, request):
        browser_family = request.user_agent.browser.family
        return "Chrome" in browser_family

    def is_mobile(self, request):
        return request.user_agent.is_mobile
    
    def global_context_flags(self, request):
        context = {}
        context["study_duration_days"] = STUDY_DURATION_DAYS
        context["study_compensation"] = STUDY_COMPENSATION
        if not self.is_chrome(request):
            context['block_next_step'] = True
            context['NOT_CHROME_ERROR'] = 'Error: You must use Google Chrome to participate in our study. Please switch browsers and try again.'
        if self.is_mobile(request):
            context['block_next_step'] = True
            context['MOBILE_ERROR'] = 'Error: Please complete the signup process on a desktop device rather than a mobile device.'
        return context
    
    # Get Experiment Member
    def get_experiment_member(self, request):
       return ExperimentMember.objects.get(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT)

    # Get or none in case they're not authenticated
    def get_experiment_member_or_none(self, request):
        if request.user.is_authenticated:
            return ExperimentMember.objects.filter(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT).first()
        return None
    
    def disable_fields(self, form):
        for field in form.fields:
            form.fields[field].widget.attrs['readonly'] = True
            form.fields[field].widget.attrs['disabled'] = True
        return form
    
    def get_onboarding_code(self, request):
        experiment_member = ExperimentMember.objects.get(social_auth=request.user)
        if OnboardCode.objects.filter(registered_user=experiment_member):
            return OnboardCode.objects.get(registered_user=experiment_member)
        return None


# Index View
class IndexView(OnboardView):
    def get_curr_str(self):
        return 'onboard:index'
    def get_curr_html(self):
        return 'onboard/index.html'
    def get_next_str(self):
        return 'onboard:demographics_prolific'
    def get_page_title(self):
        return "Join the study"
    def get_onboarding_closed(self):
        return False

    def get_context(self, request):
        # Load context from global flags
        context = self.global_context_flags(request)
        context['show_prev_step'] = False
        context['form_url'] = {'current': self.get_curr_str()}
        return context
    
    def is_eligible(self, cleaned_data):
        if not cleaned_data['us_residency']:
            return False
        if not cleaned_data['age_eligible']:
            return False
        if not cleaned_data['main_browser']:
            return False
        if not cleaned_data['informed_consent']:
            return False
        if not cleaned_data['prolific_id']:
            return False
        return True

    def get(self, request):
        context = self.get_context(request)
        form = InformedConsentForm()
        
        # If the user can't proceed because of given reason.
        if 'block_next_step' in context:
            form = self.disable_fields(form)
        
        # If the user is already authenticated, load user, pre-fill, and use.
        experiment_member = self.get_experiment_member_or_none(request)
        if experiment_member:
            context['ONBOARD_CODE_ALERT'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team.'
            prolific_id = "Prolific Id"
            if ProlificId.objects.filter(user_id=experiment_member).count():
                prolific_id = ProlificId.objects.get(user_id=experiment_member)
            form.fields['us_residency'].initial = True
            form.fields['age_eligible'].initial = True
            form.fields['main_browser'].initial = True
            form.fields['informed_consent'].initial = True
            form.fields['prolific_id'].initial = prolific_id
            form = self.disable_fields(form)

        context['form'] = form
        context['page_title'] = self.get_page_title()
        context['ONBOARDING_CLOSED'] = self.get_onboarding_closed()
        return render(request, self.get_curr_html(), context)
    
    def post(self, request):
        context = self.get_context(request)
        form = InformedConsentForm(request.POST)

        # If the person is already logged in, ignore. Proceed to the next step in the waitlist flow.
        experiment_member = self.get_experiment_member_or_none(request)
        if experiment_member:
            return redirect(self.get_next_str())

        # Check if the form is valid and the person has indicated they are eligible. If so, create the user account.
        if form.is_valid() and self.is_eligible(form.cleaned_data):
            # Store user data in session for when the user creates an account
            request.session['new_user_informed_consent'] = True
            request.session['new_user_prolific_id'] = form.cleaned_data['prolific_id']
            return redirect('social:begin', 'google-oauth2')
        else:
            # If it's not valid for whatever reason, rerender with needed fixes.
            context['form'] = form
            return render(request, self.get_curr_html(), context)

class IndexProlificView(IndexView):
    def get_curr_str(self):
        return 'onboard:index_prolific'
    def get_curr_html(self):
        return 'onboard/index.html'
    def get_next_str(self):
        return 'onboard:demographics_prolific'
    def get_page_title(self):
        return "Join the study"
    def get_onboarding_closed(self):
        return False


class DemographicsView(OnboardView):
    def get_prev_str(self):
        return 'onboard:index'
    def get_curr_str(self):
        return 'onboard:demographics_prolific'
    def get_curr_html(self):
        return 'onboard/demographics.html'
    def get_next_str(self):
        return 'onboard:pre_onboard'
    def grant_onboard_permission(self, experiment_member):
        return

    def get_context(self, request):
        # Just load context from global settings
        context = self.global_context_flags(request)
        context['show_prev_step'] = True
        context['form_url'] = {'current': self.get_curr_str(), 'previous': self.get_prev_str()}
        return context

    def get(self, request):
        context = self.get_context(request)
        form = DemographicsForm()

        # If the user can't continue, disable form and show them so
        if 'block_next_step' in context:
            form = self.disable_fields(form)
            context['form'] = form
            return render(request, self.get_curr_html(), context)
        
        # Same as above, but if they're not logged in
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member:
            form = self.disable_fields(form)
            context['form'] = form
            context['ONBOARD_CODE_ERROR'] = 'You must create your account to proceed. Please go back, confirm your eligibility, and try again.'
            context['block_next_step'] = True
            return render(request,  self.get_curr_html(), context)
        
        # Check if the user has completed a demographics form, and if so, just render that to them.
        if Demographics.objects.filter(user_id=experiment_member):
            context['ONBOARD_CODE_ALERT'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team.'
            member_demographics = Demographics.objects.get(user_id=experiment_member)
            form = DemographicsForm(instance=member_demographics)
            form.initial['race_multi_list'] = list(member_demographics.race)
            form = self.disable_fields(form)
            context['form'] = form
            return render(request,  self.get_curr_html(), context)
        
        # If that's not true either, then just render base form out.
        context['form'] = form
        return render(request,  self.get_curr_html(), context)

    def post(self, request):
        context = self.get_context(request)
        form = DemographicsForm(request.POST)

        # If the user can't continue, just ignore the request and redirect them back to the get page,
        # which will explain their error to them.
        experiment_member = self.get_experiment_member_or_none(request)
        if 'block_next_step' in context or not experiment_member:
            return redirect(self.get_curr_str())

        # If the user already has submitted a form or has an existing form, ignore them. Proceed to the next step in the waitlist flow.
        if Demographics.objects.filter(user_id=experiment_member):
            return redirect(self.get_next_str())
        
        # If these aren't true, then check form validity to proceed. If invalid, just send in to re-render.
        if form.is_valid():
            # Set fields manually and proceed to save the model
            member_demographics = form.save(commit=False)
            member_demographics.user_id = experiment_member
            member_demographics.race = ''.join(form.cleaned_data['race_multi_list'])
            member_demographics.save()

            # Grant onboard permission if coming from Prolific
            self.grant_onboard_permission(experiment_member)
            return redirect(self.get_next_str())
        else:
            context['form'] = form
            return render(request,  self.get_curr_html(), context)

class DemographicsProlificView(DemographicsView):
    def get_prev_str(self):
        return 'onboard:index_prolific'
    def get_curr_str(self):
        return 'onboard:demographics_prolific'
    def get_curr_html(self):
        return 'onboard/demographics.html'
    def get_next_str(self):
        #return 'onboard:install'
        return 'frontend:intro-survey'
    def grant_onboard_permission(self, experiment_member):
        if experiment_member.has_onboard_permission != True: # Prevent sending duplicate email to onboarded participants.
            experiment_member.has_onboard_permission = True
            experiment_member.save()

class InstallView(OnboardView):
    def get_context(self, request):
        # Load context from global flags
        context = self.global_context_flags(request)
        context['show_prev_step'] = False
        context['form_url'] = {'current': 'onboard:install'}
        return context

    def get(self, request):
        context = self.get_context(request)
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member: 
            return redirect('frontend:index')

        return render(request, 'onboard/install.html', context)
    
    def post(self, request):
        context = self.get_context(request)
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member:
            return redirect('frontend:index')

        return redirect('onboard:extension_prolific')

class ExtensionView(OnboardView):
    def get_context(self, request):
        # Just load context from global settings
        context = self.global_context_flags(request)
        # Note that here, there is no proceed button. You are automatically redirected, this is a different template.
        context['show_prev_step'] = True
        context['form_url'] = {
            'current': self.get_curr_str(),
            'previous': self.get_prev_str(),
            'link': 'onboard:extension-download',
            }
        return context
    
    def get_prev_str(self):
        return 'frontend:intro-survey'
    def get_curr_str(self):
        return 'onboard:extension'
    def get_next_str(self):
        return 'onboard:complete'
    def get_next_html(self):
        return 'onboard/extension.html'

    def get(self, request):
        context = self.get_context(request)
        form = ExtensionForm()

        # If the user can't continue, disable the form
        if 'block_next_step' in context:
            form = self.disable_fields(form)
            context['form'] = form
            return render(request, self.get_next_html(), context)
        
        # Now check if the user is not logged in
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member:
            form = self.disable_fields(form)
            context['form'] = form
            context['ONBOARD_CODE_ERROR'] = 'You must create your account to proceed. Please go back, confirm your eligibility, and try again.'
            context['block_next_step'] = True
            return render(request, self.get_next_html(), context)
        
        # Now, see if you have demographics form, otherwise remove
        if not Demographics.objects.filter(user_id=experiment_member):
            form = self.disable_fields(form)
            context['form'] = form
            context['ONBOARD_CODE_ERROR'] = 'You must fill out the demographics survey before you can proceed. Please go back and try again.'
            context['block_next_step'] = True
            return render(request, self.get_next_html(), context)
        
        # Now check the experiment member, see if you have a registered extension
        form.fields['user_id'].initial = str(experiment_member.user_id)
        form.fields['is_admin'].initial = experiment_member.social_auth.is_staff
        if experiment_member.extension_registered:
            form = self.disable_fields(form)
            context['form'] = form
            context['ONBOARD_CODE_ALERT']  = 'Your extension is already registered. Please continue, or contact the Intervenr Team with issues.'
            context['EXTENSION_REGISTERED'] = True
            context['form_url']['link'] = self.get_next_str()
            return render(request, self.get_next_html(), context)
        
        # Otherwise, if this is not registered, then, setup and push back
        context['form'] = form
        return render(request, self.get_next_html(), context)

    def post(self, request):
        context = self.get_context(request)
        form = ExtensionForm(request.POST)

        # If block next step, they're not logged in, redirect them
        experiment_member = self.get_experiment_member_or_none(request)
        if 'block_next_step' in context or not experiment_member:
            return redirect(self.get_curr_str())
        
        # Also load the experiment member, if it does not exist, redirect them
        if not Demographics.objects.filter(user_id=experiment_member):
            return redirect(self.get_curr_str())
        
        # Finally, check the user object and confirm their registration
        if form.is_valid():
            if form.cleaned_data['user_id'] == str(experiment_member.user_id):
                # Check if the user object code is right
                experiment_member.extension_registered = True
                experiment_member.save()
                return redirect(self.get_next_str())
        else:
            context['form'] = form
            context['ONBOARD_CODE_ERROR'] = 'Error: Your extension registration failed. Please reload or contact the Intervenr Team.'
            return render(request, self.get_next_html(), context)

class ExtensionProlificView(ExtensionView):
    def get_prev_str(self):
        return 'onboard:install'
    def get_curr_str(self):
        return 'onboard:extension_prolific'
    def get_next_str(self):
        return 'onboard:complete_prolific'
    def get_next_html(self):
        return 'onboard/extension_prolific.html'


class CompleteView(OnboardView):
    def get_curr_str(self):
        return 'onboard:complete'
    def get_curr_html(self):
        return 'onboard/complete.html'
    def get_redirect_str(self):
        return 'onboard:redirect'
    def get_success_str(self):
        return "Congratulations, you've completed the onboarding process! Thank you for your help and cooperation, you're now fully enrolled in the Intervenr Experiment."

    def check_all_steps(self, request):
        experiment_member = self.get_experiment_member_or_none(request)
        # Logged in or not
        if not experiment_member:
            return (False, 'Error: You must create an account, please complete this step or contact the Intervenr Team.')
        # Demographics form
        if not Demographics.objects.filter(user_id=experiment_member):
            return (False, 'Error: You must complete the demographics survey. Please complete this step or contact the Intervenr Team')
        # Registered Extension
        if not experiment_member.extension_registered:
            return (False, 'Error: You must register the Intervenr Extension. Please complete this step or contact the Intervenr Team.')
        return (True, self.get_success_str())
    
    def get(self, request):
        context = {
            'show_prev_step': False,
            'form_url': {
                'current': self.get_curr_str(),
            }
        }
        context['show_prev_step'] = False
        all_steps_complete, completion_status = self.check_all_steps(request)
        if all_steps_complete:
            context['completion_message'] = completion_status
            context['completion_link_message'] = 'Go to Home Page'
            context['form_url']['link'] = 'frontend:index'
            experiment_member = ExperimentMember.objects.get(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT)
            if not experiment_member.has_onboarded:
                experiment_member.has_onboarded = True
                experiment_member.onboard_date = datetime.datetime.now()
                experiment_member.save()
        else:
            context['ONBOARD_CODE_ERROR'] = completion_status
            context['completion_message'] = 'Uh-oh, something went wrong during your sign up process. Please fix the problems below. If you need help, please contact the Intervenr Team.'
            context['completion_link_message'] = 'Go Back'
            context['form_url']['link'] = self.get_redirect_str()
        return render(request, self.get_curr_html(), context)
    
    def post(self, request):
        # There should be no post requests to the completion page
        return redirect(self.get_curr_str())

class CompleteProlificView(CompleteView):
    def get_curr_str(self):
        return 'onboard:complete_prolific'
    def get_curr_html(self):
        return 'onboard/complete_prolific.html'
    def get_redirect_str(self):
        return 'onboard:redirect_prolific'


# Redirect will send users to the onboarding flow component they belong in.
class RedirectView(OnboardView):
    def get(self, request):
        experiment_member = self.get_experiment_member_or_none(request)
        # If not logged in, send back to initial screen.
        if not experiment_member:
            return redirect('onboard:index')
        
        # If logged in, but demographics form not filled out, redirect to demographics.
        if not Demographics.objects.filter(user_id=experiment_member):
            return redirect('onboard:demographics_prolific')

        elif not experiment_member.has_onboard_permission:
            return redirect('onboard:pre_onboard')

        # If logged in + demographics filled, then check if extension has been registered.
        if not experiment_member.extension_registered:
            return redirect('onboard:extension')
        
        # If all of these conditions are met, redirect them to the end of the onboarding flow.
        return redirect('onboard:complete')

class RedirectProlificView(OnboardView):
    def get(self, request):
        experiment_member = self.get_experiment_member_or_none(request)
        # If not logged in, send back to initial screen.
        if not experiment_member:
            return redirect('onboard:index_prolific')
        
        # If logged in, but demographics form not filled out, redirect to demographics.
        if not Demographics.objects.filter(user_id=experiment_member):
            return redirect('onboard:demographics_prolific')

        elif not experiment_member.has_onboarded:
            return redirect('onboard:install')

        # If logged in + demographics filled, then check if extension has been registered.
        if not experiment_member.extension_registered:
            return redirect('onboard:extension_prolific')
        
        # If all of these conditions are met, redirect them to the end of the onboarding flow.
        return redirect('onboard:complete_prolific')

# Redirect Extension Link
def extension_download(request):
    return redirect('https://drive.google.com/file/d/1lUFZixAb_rpTh_mEUjGJ4I0CsN5JZ-sc/view?usp=sharing')

# PreOnboardView
class PreOnboardView(OnboardView):
    def get_context(self, request):
        # Load context from global flags
        context = self.global_context_flags(request)
        return context

    def get(self, request):
        context = self.get_context(request)
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member: 
            return redirect('frontend:index')

        return render(request, 'onboard/pre_onboard.html', context)


# StartOnboardView
class StartOnboardView(OnboardView):
    def get_context(self, request):
        # Load context from global flags
        context = self.global_context_flags(request)
        context['show_prev_step'] = False
        context['form_url'] = {'current': 'onboard:start_onboard'}
        return context

    def get(self, request):
        context = self.get_context(request)
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member: 
            return redirect('frontend:index')

        return render(request, 'onboard/start_onboard.html', context)
    
    def post(self, request):
        context = self.get_context(request)
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member:
            return redirect('frontend:index')

        return redirect('frontend:intro-survey')
