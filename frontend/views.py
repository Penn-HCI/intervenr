from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.http import FileResponse, StreamingHttpResponse
from django.views import View
import django.db.models as djModels
from django.db.models import Count
from frontend import models as frontend_models
from extension import models as extension_models
from ads_extension import models as ads_extension_models
from onboard import models as onboard_models
from onboard.pipeline import CURRENT_EXPERIMENT
from frontend import forms
import pandas as pd
import datetime
import uuid
import math
import json
import random
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from intervenr.settings.base import RUNNING_PROD
from smtplib import SMTPException
from django.core.paginator import Paginator
from ipware import get_client_ip
import os
from django.conf import settings
import pickle


# Filter to only images downloaded to S3 if running on production
FILT_TO_DOWNLOADED = RUNNING_PROD
AUTO_EMAILS_ENABLED = False

cached_sampled_ads = {}
cached_final_sampled_ads = {}

# with open(os.path.join(settings.STATIC_ROOT, 'data/22_07_25_sampled_ads.pkl'), "rb") as f:
#     cached_sampled_ads = pickle.load(f)

# with open(os.path.join(settings.STATIC_ROOT, 'data/22_08_02_sampled_ads_finalSurv.pkl'), "rb") as f:
#     cached_final_sampled_ads = pickle.load(f)

# Baseclass Frontend View
class FrontEndView(View):
    # batch size
    BATCH_SIZE = 1500

    # identify person is staff
    def is_simple_admin(self, request):
        return request.user.is_authenticated and request.user.is_staff

    # Get Experiment Member
    def get_experiment_member(self, request):
       return frontend_models.ExperimentMember.objects.get(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT)

    # Get or none in case they're not authenticated
    def get_experiment_member_or_none(self, request):
        if request.user.is_authenticated:
            return frontend_models.ExperimentMember.objects.filter(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT).first()
        return None

    # Try to stream the response (speed up downloads)
    def get_stream_http(self, yield_csv_func, filename):
        response = StreamingHttpResponse(
            yield_csv_func(),
            content_type = 'text/csv',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    def disable_fields(self, form):
        for field in form.fields:
            form.fields[field].widget.attrs['readonly'] = True
            form.fields[field].widget.attrs['disabled'] = True
        return form

    """
    auto offboard participants, example of what an actually implemented function would look like with 8 day runtime.
    NOTE: Not actually implemented, just code example.
    """
    def auto_offboard_user(self, request):
        user = self.get_experiment_member_or_none(request)
        if not user or (user.creation_date - datetime.date.today()).days <= 8:
            return False
        user.offboard_user = True
        user.offboard_date = datetime.datetime.now()
        user.save()
        return True


# Index Page
class IndexView(FrontEndView):
    # Simple inauthenticated page
    def get_req_inauth(self, request):
        return render(request, 'frontend/index.html', {})

    # Get study context cor complex authentication page
    def get_study_context(self, context):
        experiment_member = context['experiment_member']
        context['study_start_date'] = experiment_member.creation_date.strftime('%A, %B %-d')

        experiment_type = experiment_member.experiment_type
        if experiment_type == frontend_models.ExperimentTypes.NEWS:
            context['experiment_type'] = "News Media"
        elif experiment_type == frontend_models.ExperimentTypes.ADS:
            context['experiment_type'] = "Ads"
        else:
            context['experiment_type'] = ""

        if not experiment_member.offboard_user:
            context['study_duration_days'] = (datetime.date.today() - experiment_member.creation_date.date()).days
        else:
            context['study_duration_days'] = (experiment_member.offboard_date.date() - experiment_member.creation_date.date()).days
        return context

    # Get personalized data (news)
    def get_user_data(self, request, context):
        # Load user
        experiment_member = context['experiment_member']
        # Hard code page size to be 25 max
        page_size = 25

        # Get the total number of records for the user
        context['total_url_records'] = extension_models.UrlRecord.objects.filter(participant_id=experiment_member).count() - 1
        # Get total number of pages
        context['total_url_record_pages'] = int(context['total_url_records'] / page_size)

        # Get what page and number of requests to show on the user page, add it to context
        page_num = int(request.GET.get('pg',0))
        page_num = page_num if page_num < context['total_url_record_pages'] else context['total_url_record_pages']
        # Setup current page
        context['current_page_num'] = page_num

        # Now finally, send the requested URL Records in
        url_records = extension_models.UrlRecord.objects.filter(participant_id=experiment_member).order_by('-start_time')[page_num * page_size:page_num * page_size + page_size]
        context['url_records'] = url_records
        # lastly, add the form for getting data
        context['url_form'] = forms.UrlRedactionForm()

        return context

    # Get personalized data (ads)
    def get_ads_user_data(self, request, context):
        # Load user
        experiment_member = context['experiment_member']
        # Hard code page size to be 25 max
        page_size = 25

        # Get the total number of records for the user
        ad_records_ct = ads_extension_models.AdRecord.objects.filter(participant_id=experiment_member).values("src_page_url", "page_domain", "src_page_title", "created_time__date", "created_time__hour", "created_time__minute").annotate(ad_count=Count("ad_hash")).order_by("-created_time__date", "-created_time__hour", "-created_time__minute", '-src_page_url').count()
        context['total_ad_records'] = ad_records_ct - 1
        
        # Get total number of pages
        context['total_ad_record_pages'] = int(context['total_ad_records'] / page_size)

        # Get what page and number of requests to show on the user page, add it to context
        page_num = int(request.GET.get('pg',0))
        page_num = page_num if page_num < context['total_ad_record_pages'] else context['total_ad_record_pages']
        # Setup current page
        context['current_page_num'] = page_num

        # Now finally, send the requested URL Records in
        ad_records = ads_extension_models.AdRecord.objects.filter(participant_id=experiment_member).values("src_page_url", "page_domain", "src_page_title", "created_time__date", "created_time__hour", "created_time__minute").annotate(ad_count=Count("ad_hash")).order_by("-created_time__date", "-created_time__hour", "-created_time__minute", '-src_page_url')[page_num * page_size:page_num * page_size + page_size]

        context['ad_records'] = ad_records
        # lastly, add the form for getting data
        context['ad_form'] = forms.AdRedactionForm()

        return context

    # Contact Email Context
    def get_contact_email(self, context):
        context['contact_email'] = context['experiment_member'].contact_email
        context['contact_email_form'] = forms.ContactEmailForm()
        return context

    # More complex authenticated page
    def get_req_auth(self, request, experiment_member):
        context = {}
        # Fetch page for another user (admin only)
        experimentmember_param = request.GET.get('experimentmember')
        if (experimentmember_param is not None) and (experiment_member.social_auth.is_staff):
            # Fetch information for provided experiment member
            experiment_member = frontend_models.ExperimentMember.objects.get(user_id=experimentmember_param, experiment_type=CURRENT_EXPERIMENT)

        context['experiment_member'] = experiment_member
        context['participant_id'] = str(experiment_member.user_id)
        context["is_admin"] = experiment_member.social_auth.is_staff

        if not onboard_models.Demographics.objects.filter(user_id=experiment_member):
            # Direct to post-google-auth portion of waitlist flow
            return redirect('onboard:demographics_prolific')
        elif not experiment_member.has_onboard_permission:
            return redirect('onboard:pre_onboard')
        elif not experiment_member.has_onboarded:
            return redirect('onboard:start_onboard')
        else:
            context = self.get_study_context(context)
            context = self.get_contact_email(context)
            if experiment_member.experiment_type == frontend_models.ExperimentTypes.NEWS:
                context = self.get_user_data(request, context)
                return render(request, 'frontend/index.html', context)
            elif experiment_member.experiment_type == frontend_models.ExperimentTypes.ADS:
                context = self.get_ads_user_data(request, context)
                # Get IP address and store
                # client_ip, _ = get_client_ip(request)
                # if client_ip is not None:
                #     new_ip = ads_extension_models.ClientIP.objects.get_or_create(
                #         ip=client_ip,
                #         participant_id=experiment_member, 
                #     )
                return render(request,'frontend/index_ads.html', context)

    # Basic Get
    def get(self, request):
        experiment_member = self.get_experiment_member_or_none(request)
        if not experiment_member:
            return self.get_req_inauth(request)
        else:
            return self.get_req_auth(request, experiment_member)


# User Delete URL Record
class UserDeleteUrlRecord(FrontEndView):
    # Check and delete record
    def check_and_del(self, experiment_member, url_record):
        url_uuid = uuid.UUID(url_record)
        if extension_models.UrlRecord.objects.filter(participant_id=experiment_member, record_id=url_uuid):
            record = extension_models.UrlRecord.objects.get(participant_id=experiment_member, record_id=url_uuid)
            # Now get Visible Link Records to delete
            extension_models.VisibleLinkRecord.objects.filter(participant_id=experiment_member, parent_page_url_record=record).delete()
            # Now get Tweet Records to delete
            extension_models.TweetRecord.objects.filter(participant_id=experiment_member, parent_page_url_record=record).delete()
            # Then delete the object itself
            record.delete()

    # The post request delete
    def post(self, request):
        # get the form and bind it
        url_form = forms.UrlRedactionForm(request.POST)
        page_num = None

        # Clean / check the form is valid, confirm user exists
        experiment_member = self.get_experiment_member_or_none(request)
        if experiment_member and url_form.is_valid():
            # get the page value
            page_num = int(url_form.cleaned_data['redaction_list']['pg'])
            # Now for each request, see if the json request is valid, and then run the delete function on it
            for url_record in url_form.cleaned_data['redaction_list']['urlRecords']:
                self.check_and_del(experiment_member, url_record)

        # Build the parameters and response
        response = redirect('frontend:index')
        if page_num:
            response['Location'] += f'?pg={page_num}'
        return response

# User Delete Ad Record
class UserDeleteAdRecord(FrontEndView):
    # Check and delete record
    def check_and_del(self, experiment_member, ad_record):
        src_page_url = ad_record["src_page_url"]
        created_time__date = ad_record["created_time__date"]
        created_time__hour = ad_record["created_time__hour"]
        created_time__minute = ad_record["created_time__minute"]

        records = ads_extension_models.AdRecord.objects.filter(participant_id=experiment_member, src_page_url=src_page_url, created_time__date=created_time__date, created_time__hour=created_time__hour, created_time__minute=created_time__minute)
        n_deleted = len(records)
        for record in records:
            record.delete()
        
        new_redaction = ads_extension_models.AdRecordRedaction(
            participant_id=experiment_member,
            n_deleted=n_deleted,
        )
        new_redaction.save()

    # The post request delete
    def post(self, request):
        # get the form and bind it
        ad_form = forms.AdRedactionForm(request.POST)
        page_num = None

        # Clean / check the form is valid, confirm user exists
        experiment_member = self.get_experiment_member_or_none(request)
        if experiment_member and ad_form.is_valid():
            # get the page value
            page_num = int(ad_form.cleaned_data['redaction_list']['pg'])
            # Now for each request, see if the json request is valid, and then run the delete function on it
            for ad_record in ad_form.cleaned_data['redaction_list']['urlRecords']:
                self.check_and_del(experiment_member, ad_record)

        # Build the parameters and response
        response = redirect('frontend:index')
        if page_num:
            response['Location'] += f'?pg={page_num}'
        return response

# User Update Email
class UserUpdateEmail(FrontEndView):
    # post request for email only
    def post(self, request):
        contact_email_form = forms.ContactEmailForm(request.POST)
        # Clean and check the form is valid, confirm user exists
        experiment_member = self.get_experiment_member_or_none(request)
        if experiment_member and contact_email_form.is_valid():
            experiment_member.contact_email = contact_email_form.cleaned_data['contact_email']
            experiment_member.save()
        return redirect('frontend:index')


# Simple Admin
class SimpleAdmin(FrontEndView):
    # This is a wrapper for the generic operation of taking a given queryset, and showing a paginated version
    # for the simple admin template page
    def get_context_paginate_query(self, queryset, context_name, context, pg=0, pgsize=25):
        pg = int(pg)
        context[f'{context_name}_count'] = queryset.count()
        context[f'{context_name}_curr_page'] = pg
        context[f'{context_name}_total_pages'] = int((queryset.count() - 1)/ pgsize)
        context[f'{context_name}_list'] = queryset[pg * pgsize:pg * pgsize + pgsize]
        return context

    # First of the heap, get experiment participant context
    def get_experiment_participant_context(self, request, context):
        # Simple query for all experiment members, list their count
        all_experiment_members = frontend_models.ExperimentMember.objects.all()
        # Get what page
        curr_page = request.GET.get('expg', 0)
        context = self.get_context_paginate_query(all_experiment_members, 'experiment_members', context, pg=curr_page)
        return context

    # Second in the heap, get TLD records
    def get_tld_record_context(self, request, context):
        # get all the TLD records
        all_tld_records = extension_models.TldRecord.objects.all()
        # Get what page
        curr_page = request.GET.get('tldpg', 0)
        context = self.get_context_paginate_query(all_tld_records, 'tld_records', context, pg=curr_page)
        return context

    # Third in the heap, get URL records
    def get_url_record_context(self, request, context):
        # get all the URL records
        all_url_records = extension_models.UrlRecord.objects.all()
        # Get page num
        curr_page = request.GET.get('urlpg', 0)
        context = self.get_context_paginate_query(all_url_records, 'url_records', context, pg=curr_page)
        return context

    # Fourth in the heap, get daily intervention counts
    def get_intervention_counts_context(self, request, context):
        # get all intervention counts
        all_intervention_counts = extension_models.DailyInterventionCount.objects.all()
        # get page num
        curr_page = request.GET.get('intpg', 0)
        context = self.get_context_paginate_query(all_intervention_counts, 'intervention_counts', context, pg=curr_page)
        context['intervention_counts_sum'] = all_intervention_counts.filter(tld_record__apply_intervention=True).values('date__date').annotate(all_visits=djModels.Sum('visit_count')).aggregate(SUM=djModels.Sum('all_visits'))['SUM']
        return context

    # Fifth in the heap, get visible link records
    def get_visible_link_records_context(self, request, context):
        # get the visible link records
        all_visible_records = extension_models.VisibleLinkRecord.objects.all()
        # get page num
        curr_page = request.GET.get('vispg', 0)
        context = self.get_context_paginate_query(all_visible_records, 'visible_records', context, pg=curr_page)
        return context

    # Add all the backend update functions here
    def get(self, request):
        if self.is_simple_admin(request):
            context = {}
            context = self.get_experiment_participant_context(request, context)
            context = self.get_tld_record_context(request, context)
            context = self.get_url_record_context(request, context)
            context = self.get_intervention_counts_context(request, context)
            context = self.get_visible_link_records_context(request, context)
            context['json_data_submit_form'] = forms.SAJsonDataForm()
            return render(request, 'frontend/simple_admin.html', context)
        return redirect('frontend:index')

# Dashboard
class Dashboard(FrontEndView):
    # Helper function to return active participants
    def fetch_active_partipants(self):
        experiment_members = frontend_models.ExperimentMember.objects.filter(experiment_type=frontend_models.ExperimentTypes.ADS).filter(has_onboard_permission=True).filter(social_auth__is_staff=False).filter(offboard_user=False).values() # Only includes Intervenr Ads participants
        return experiment_members

    def fetch_ineligible_survey_users(self):
        check_eligibility_bool = self.request.GET.get('checkEligibility', None)
        ineligible_mid_survey_users = []
        ineligible_final_survey_users = []
        mid_survey = MidpointSurvey()
        final_survey = FinalSurvey()
        if check_eligibility_bool is not None:
            if check_eligibility_bool.lower() == "true":
                experiment_members = self.fetch_active_partipants()
                for experiment_member in experiment_members:
                    if mid_survey.is_eligible(experiment_member['user_id']) is False:
                        ineligible_mid_survey_users.append(experiment_member['contact_email'])
                    if final_survey.is_eligible(experiment_member['user_id']) is False:
                        ineligible_final_survey_users.append(experiment_member['contact_email'])

                ineligible_survey_users = {'ineligible_mid_survey_users': ', '.join([email for email in ineligible_mid_survey_users]),'ineligible_mid_survey_users_cnt': len(ineligible_mid_survey_users), 'ineligible_final_survey_users': ', '.join([email for email in ineligible_final_survey_users]), 'ineligible_final_survey_users_cnt': len(ineligible_final_survey_users)}
                return ineligible_survey_users
            else:
                return None 

    def get_survey_summary(self):
        incomplete_midpoint = self.fetch_active_partipants().filter(middle_survey=False)
        incomplete_final = self.fetch_active_partipants().filter(offboard_survey=False)
        survey_summary_stats = {'incomplete_midpoint': "None" if incomplete_midpoint.count() == 0 else ', '.join([i['contact_email'] for i in incomplete_midpoint.values()]), 'incomplete_midpoint_cnt': incomplete_midpoint.count(), 'incomplete_final': "None" if incomplete_final.count() == 0 else ', '.join([i['contact_email'] for i in incomplete_final.values()]),'incomplete_final_cnt': incomplete_final.count()}
        return survey_summary_stats

    # Add user specific stats to a list
    def get_dashboard_stats(self, request):
        experiment_members = self.fetch_active_partipants() # Only includes Intervenr Ads participants
        dashboard_stats = []

        for exp_member in experiment_members:
            cur_stats = {}
            # Contact Email
            cur_stats['contact_email'] = exp_member['contact_email']
            # Total ads collected so far
            cur_stats["total_ads"] = ads_extension_models.AdRecord.objects.filter(participant_id=exp_member['user_id']).count()
            creation_date = exp_member['creation_date']
            experiment_days = (datetime.datetime.now() - creation_date).days
            # Average Ads / Day
            cur_stats["avg_daily_ads"] =round(cur_stats["total_ads"] / experiment_days, 2) if (experiment_days != 0) else 0
            # Ad Count Today
            cur_stats["today_ads"] = ads_extension_models.AdRecord.objects.filter(participant_id=exp_member['user_id']).filter(created_time__date=datetime.date.today()).count()
            # Swap Partner Email
            swap_partner_id = exp_member["swap_partner_id"]
            if swap_partner_id is not None:
                swap_partner = frontend_models.ExperimentMember.objects.get(user_id=swap_partner_id).contact_email
            else:
                swap_partner = None
            cur_stats["swap_partner_email"] = swap_partner
            # Has Onboard Permission (Boolean)
            cur_stats['has_onboard_permission'] = exp_member['has_onboard_permission']
            # Has Onboarded (Boolean)
            cur_stats['has_onboarded'] = exp_member['has_onboarded']
            # Has Offboarded (Boolean)
            cur_stats['has_offboarded'] = exp_member['offboard_user']
            # Intro Survey Filled? (Boolean)
            cur_stats['intro_survey_bool'] = exp_member['onboard_survey']
            # Midpoint Survey Filled? (Boolean)
            cur_stats['midpoint_survey_bool'] = exp_member['middle_survey']
            cur_stats['midpoint_survey_link'] = f"/midpoint-survey/?experimentmember={exp_member['user_id']}"
            # Final Survey Filled? (Boolean)
            cur_stats['final_survey_bool'] = exp_member['offboard_survey']
            # Experiment Type
            cur_stats['final_survey_link'] = f"/final-survey/?experimentmember={exp_member['user_id']}"
            cur_stats['experiment_type'] = 'News Media' if exp_member['experiment_type'] == frontend_models.ExperimentTypes.NEWS else ('Intervenr Ads' if exp_member['experiment_type'] == frontend_models.ExperimentTypes.ADS else 'Undefined')
            # TODO: Experimental Condition
            # Add experiment member's stats to list
            dashboard_stats.append(cur_stats)
        paginator = Paginator(dashboard_stats, 60) # Show 60 experiment members per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        return dashboard_stats, page_obj

    def get_graph_stats(self):
        graph_stats = {}
        # graph_stats = {'y-axis': [adcount1, adcount2, adcount3, adcount4], 'x-axis': [date1, date2, date3]}
        today = datetime.date.today()
        x_axis = [today-datetime.timedelta(i) for i in range(9, -1, -1)]
        y_axis = []

        exp_members = self.fetch_active_partipants()
        exp_member_ids = exp_members.values_list("user_id", flat=True)

        for date in x_axis:
            # includes only users that were offboarded after the given `date` or not offboarded yet
            cur_day_exp_mem_count = exp_members.filter(offboard_date__gte=date).count() + exp_members.filter(offboard_date=None).count()
            if cur_day_exp_mem_count != 0:
                cur_day_ads = ads_extension_models.AdRecord.objects.filter(created_time__date=date).filter(participant_id__in=exp_member_ids).count()
                cur_avg_ads_per_mem = cur_day_ads / cur_day_exp_mem_count
                y_axis.append(cur_avg_ads_per_mem)
            else:
                y_axis.append(0)
        graph_stats['x_axis'] = x_axis
        graph_stats['y_axis'] = y_axis
        return graph_stats

    def get_quick_dash_insights(self):
        exp_members = self.fetch_active_partipants()
        total_exp_mems_cnt = exp_members.count()
        onboarded_mems_cnt = exp_members.filter(has_onboarded=True).count()
        offboard_mems_cnt = exp_members.filter(offboard_user=True).count()
        waitlisted_mems_cnt = frontend_models.ExperimentMember.objects.filter(has_onboard_permission=False).filter(social_auth__is_staff=False).filter(experiment_type=frontend_models.ExperimentTypes.ADS).count()
        total_ad_cnt = ads_extension_models.AdRecord.objects.all().count
        quick_dash_insights = {'total_exp_mems_cnt': total_exp_mems_cnt, 'onboarded_mems_cnt': onboarded_mems_cnt, 'offboard_mems_cnt': offboard_mems_cnt, 'waitlisted_mems_cnt': waitlisted_mems_cnt, 'total_ad_cnt': total_ad_cnt}
        return quick_dash_insights
        
    def get(self, request):
        if self.is_simple_admin(request):
            context = {}
            # context['exp_members_stats'], context['page_obj'] = self.get_dashboard_stats(request)
            # context['graph_stats'] = self.get_graph_stats()
            # context['quick_dash_insights'] = self.get_quick_dash_insights()
            context['survey_summary_stats'] = self.get_survey_summary()
            context['fetch_ineligible_survey_users'] = self.fetch_ineligible_survey_users()
            return render(request, 'frontend/dashboard.html', context)
        return redirect('frontend:index')


# Analysis dashboard
class AnalysisDashboard(FrontEndView):
    def get(self, request):
        if self.is_simple_admin(request):
            context = {}
            limit = 50
            view_type = request.GET.get("view_type")
            curr_target_domain = request.GET.get("target_domain")
            curr_page_domain = request.GET.get("page_domain")
            curr_ad_type = request.GET.get("content_type")
            curr_user = request.GET.get("participant_id")
            curr_phase = request.GET.get("phase")

            if view_type == None:
                view_type = "TABLE"
            if curr_target_domain != None:
                context['ads'] = ads_extension_models.AdRecord.objects.filter(target_domain = curr_target_domain)[:limit]
            elif curr_page_domain != None:
                context['ads'] = ads_extension_models.AdRecord.objects.filter(page_domain = curr_page_domain)[:limit]
            elif curr_ad_type != None:
                context['ads'] = ads_extension_models.AdRecord.objects.filter(content_type = curr_ad_type)[:limit]
            elif curr_user != None:
                context['ads'] = ads_extension_models.AdRecord.objects.filter(participant_id = curr_user)[:limit]
                swap_partner = frontend_models.ExperimentMember.objects.get(user_id = curr_user).swap_partner
            elif curr_phase != None:
                curr_phase = int(curr_phase)
                if curr_phase == 0:
                    phase_type = ads_extension_models.IntervenrAdTypes.OBS
                elif curr_phase == 1:
                    phase_type = ads_extension_models.IntervenrAdTypes.INTERV_ORIG
                elif curr_phase == 2:
                    phase_type = ads_extension_models.IntervenrAdTypes.INTERV_SWAP
                context['ads'] = ads_extension_models.AdRecord.objects.filter(intervenr_ad_type = phase_type)[:limit]
            else:
                context['ads'] = ads_extension_models.AdRecord.objects.all()[:limit]

            context['ad_count'] = ads_extension_models.AdRecord.objects.all().count
            context['view_type'] = view_type
            context['target_domain_opts'] = ads_extension_models.AdRecord.objects.order_by().values_list('target_domain', flat=True).distinct()
            context['page_domain_opts'] = ads_extension_models.AdRecord.objects.order_by().values_list('page_domain', flat=True).distinct()
            context['content_type'] = ads_extension_models.AdRecord.objects.order_by().values_list('content_type', flat=True).distinct()
            context['user_opts'] = ads_extension_models.AdRecord.objects.order_by().values_list('participant_id', flat=True).distinct()
            context['phases'] = ads_extension_models.IntervenrAdTypes.choices            
            return render(request, 'frontend/analysis_dashboard.html', context)
        return redirect('frontend:index')

# Simple Admin Download Participant Data
class SADownloadParticipants(FrontEndView):
    # Get base participant date for streaming response
    def get_streamed_participant_data(self):
        label_list = [
            'user_id',
            'creation_date',
            'is_offboarded',
            'offboarded_date',
            'intervention_type',
            'age',
            'gender',
            'race_all',
            'race_white',
            'race_black',
            'race_american_indian_alaska_native',
            'race_pacific_islander_native_hawaiian',
            'race_asian_asian_american',
            'race_other',
            'state',
            'zipcode',
            'zip_type',
            'zip_is_commissioned',
            'zip_primary_city',
            'zip_state',
            'zip_county',
            'zip_latitude',
            'zip_longitude',
            'education',
            'household_income',
            'political_ideology',
            'political_party',
            'past_voting',
            'political_engagement',
        ]
        output_str = ''
        for elem in label_list:
            output_str += f'{elem},'
        output_str = output_str[:-1]
        yield output_str
        output_str = ''

        # counter to speed up a little bit
        count = 0

        participants_data_query = list(frontend_models.ExperimentMember.objects.all())
        for participant in participants_data_query:
            # count increased at the beginning, slight edit here
            count += 1

            # For each participant, build up their basic info dict
            participant_dict = {
                'user_id': str(participant.user_id),
                'creation_date': participant.creation_date.strftime('%c'),
                'is_offboarded': participant.offboard_user,
                'offboard_date': participant.offboard_date,
                'intervention_type': participant.intervention_type,
            }
            # Now also add in all demographic information for each person
            participant_demographics = onboard_models.Demographics.objects.get(user_id=participant)
            # Now add in information from their zip codes
            participant_zip_data = onboard_models.ZipCodeInfo.objects.get(zip=participant_demographics.zipcode)
            # Update the dict with this
            participant_dict.update({
                'age': participant_demographics.get_age_display(),
                'gender': participant_demographics.get_gender_display(),
                'race_all': participant_demographics.race,
                'race_white': 'W' in participant_demographics.race,
                'race_black': 'B' in participant_demographics.race,
                'race_american_indian_alaska_native': 'N' in participant_demographics.race,
                'race_pacific_islander_native_hawaiian': 'P' in participant_demographics.race,
                'race_asian_asian_american': 'A' in participant_demographics.race,
                'race_other': 'O' in participant_demographics.race,
                'state': participant_demographics.get_state_display(),
                'zipcode': participant_demographics.zipcode,
                'zip_type': participant_zip_data.zip_type,
                'zip_is_commissioned': participant_zip_data.is_decommissioned,
                'zip_primary_city': participant_zip_data.primary_city,
                'zip_state': participant_zip_data.state,
                'zip_county': participant_zip_data.county,
                'zip_latitude': participant_zip_data.latitude,
                'zip_longitude': participant_zip_data.longitude,
                'education': participant_demographics.get_education_display(),
                'household_income': participant_demographics.get_household_income_display(),
                'political_ideology': participant_demographics.get_pol_ideology_display(),
                'political_party': participant_demographics.get_pol_party_display(),
                'past_voting': participant_demographics.get_past_voting_display(),
                'political_engagement': participant_demographics.get_pol_engagement_display(),
            })

            # Now add this to the update
            output_str += '\n'
            for key in participant_dict:
                if ',' in str(participant_dict[key]):
                    output_str += f'"{participant_dict[key]}",'
                else:
                    output_str += f'{participant_dict[key]},'
            output_str = output_str[:-1]

            # check if this count has 100, write it out then
            if count % FrontEndView.BATCH_SIZE == 0:
                final_str = output_str
                output_str = ''
                yield final_str

        if output_str != '':
            yield output_str

    # Now get all participant data -- this is both the demographics info for each person, and their basic registration info
    def get_participant_data(self):
        csv_rows_list = []
        participants_data_query = frontend_models.ExperimentMember.objects.all()
        for participant in participants_data_query:
            # For each participant, build up their basic info dict
            participant_dict = {
                'user_id': str(participant.user_id),
                'creation_date': participant.creation_date.strftime('%c'),
                'is_offboarded': participant.offboard_user,
                'offboard_date': participant.offboard_date,
                'intervention_type': participant.intervention_type,
            }
            # Now also add in all demographic information for each person
            participant_demographics = onboard_models.Demographics.objects.get(user_id=participant)
            # Now add in information from their zip codes
            participant_zip_data = onboard_models.ZipCodeInfo.objects.get(zip=participant_demographics.zipcode)
            # Update the dict with this
            participant_dict.update({
                'age': participant_demographics.get_age_display(),
                'gender': participant_demographics.get_gender_display(),
                'race_all': participant_demographics.race,
                'race_white': 'W' in participant_demographics.race,
                'race_black': 'B' in participant_demographics.race,
                'race_american_indian_alaska_native': 'N' in participant_demographics.race,
                'race_pacific_islander_native_hawaiian': 'P' in participant_demographics.race,
                'race_asian_asian_american': 'A' in participant_demographics.race,
                'race_other': 'O' in participant_demographics.race,
                'state': participant_demographics.get_state_display(),
                'zipcode': participant_demographics.zipcode,
                'zip_type': participant_zip_data.zip_type,
                'zip_is_commissioned': participant_zip_data.is_decommissioned,
                'zip_primary_city': participant_zip_data.primary_city,
                'zip_state': participant_zip_data.state,
                'zip_county': participant_zip_data.county,
                'zip_latitude': participant_zip_data.latitude,
                'zip_longitude': participant_zip_data.longitude,
                'education': participant_demographics.get_education_display(),
                'household_income': participant_demographics.get_household_income_display(),
                'political_ideology': participant_demographics.get_pol_ideology_display(),
                'political_party': participant_demographics.get_pol_party_display(),
                'past_voting': participant_demographics.get_past_voting_display(),
                'political_engagement': participant_demographics.get_pol_engagement_display(),
            })
            # Now add this to the update
            csv_rows_list += [participant_dict]
        csv_dataframe = pd.DataFrame(csv_rows_list)
        return csv_dataframe.to_csv(index=False)

    # get request the only thing defined
    def get(self, request):
        # Note: only using streamed HTTP response, could switch to standard http responses (fileresponse) if wanted
        if self.is_simple_admin(request):
            return self.get_stream_http(self.get_streamed_participant_data, 'participants_data.csv')
        return redirect('frontend:index')


# Simple Admin Download URL Records
class SADownloadUrlRecords(FrontEndView):
    # get the streamable URL Records Data
    def get_streamed_url_record_data(self):
        labels = [
            'participant_id',
            'record_id',
            'previous_record',
            'has_previous_record',
            'url',
            'tld',
            'apply_intervention',
            'apply_collect_links',
            'transition_type',
            'start_time',
            'end_time',
        ]
        output_str = ''
        for elem in labels:
            output_str += f'{elem},'
        output_str = output_str[:-1]
        yield output_str
        output_str = ''

        # count
        count = 0

        url_records_query = list(extension_models.UrlRecord.objects.all())
        for url_record in url_records_query:
            # count increase
            count += 1

            # get URL record dict
            experiment_member = url_record.participant_id
            url_record_dict = {
                'participant_id': str(experiment_member.user_id),
                'record_id': str(url_record.record_id),
                'previous_record': str(url_record.previous_record.record_id) if url_record.previous_record else '',
                'has_previous_record': url_record.has_previous_record,
                'url': url_record.url,
                'tld': url_record.tld,
                'apply_intervention': url_record.tld_record.apply_intervention if url_record.tld_record else False,
                'apply_collect_links': url_record.tld_record.apply_collect_links if url_record.tld_record else False,
                'transition_type': url_record.transition_type,
                'start_time': url_record.start_time.strftime('%c') if url_record.start_time else 'N/A',
                'end_time': url_record.end_time.strftime('%c') if url_record.end_time else 'N/A',
            }
            output_str += '\n'
            for key in url_record_dict:
                if ',' in str(url_record_dict[key]):
                    output_str += f'"{url_record_dict[key]}",'
                else:
                    output_str += f'{url_record_dict[key]},'
            output_str = output_str[:-1]

            if count % FrontEndView.BATCH_SIZE == 0:
                final_str = output_str
                output_str = ''
                yield final_str

        if output_str != '':
            yield output_str

    # get the URL Records Data
    def get_url_records_data(self):
        csv_rows_list = []
        url_records_query = extension_models.UrlRecord.objects.all()
        for url_record in url_records_query:
            # get URL record dict
            experiment_member = url_record.participant_id
            url_record_dict = {
                'participant_id': str(experiment_member.user_id),
                'record_id': str(url_record.record_id),
                'previous_record': str(url_record.previous_record.record_id) if url_record.previous_record else '',
                'has_previous_record': url_record.has_previous_record,
                'url': url_record.url,
                'tld': url_record.tld,
                'apply_intervention': url_record.tld_record.apply_intervention if url_record.tld_record else False,
                'apply_collect_links': url_record.tld_record.apply_collect_links if url_record.tld_record else False,
                'transition_type': url_record.transition_type,
                'start_time': url_record.start_time.strftime('%c') if url_record.start_time else 'N/A',
                'end_time': url_record.end_time.strftime('%c') if url_record.end_time else 'N/A',
            }
            csv_rows_list += [url_record_dict]
        csv_dataframe = pd.DataFrame(csv_rows_list)
        return csv_dataframe.to_csv(index=False)

    # get request the only thing defined
    def get(self, request):
        if self.is_simple_admin(request):
            return self.get_stream_http(self.get_url_records_data, 'url_records_data.csv')
        return redirect('frontend:index')


# Simple Admin Download Intervention Counts
class SADownloadInterventionCounts(FrontEndView):
    # big streaming response
    def get_streamed_intervention_count_data(self):
        labels = [
            'participant_id',
            'date',
            'tld',
            'apply_intervention',
            'apply_collect_links',
            'visit_count',
            'intervention_type',
        ]
        output_str = ''
        for elem in labels:
            output_str += f'{elem},'
        output_str = output_str[:-1]
        yield output_str
        output_str = ''

        # count
        count = 0

        intervention_counts_query = list(extension_models.DailyInterventionCount.objects.all())
        for counter in intervention_counts_query:
            count += 1

            experiment_member = counter.participant_id
            counter_dict = {
                'participant_id': str(experiment_member.user_id),
                'date': counter.date.strftime('%x'),
                'tld': counter.tld_record.tld if counter.tld_record else '',
                'apply_intervention': counter.tld_record.apply_intervention if counter.tld_record else False,
                'apply_collect_links': counter.tld_record.apply_collect_links if counter.tld_record else False,
                'visit_count': counter.visit_count,
                'intervention_type': counter.intervention_type,
            }
            output_str += '\n'
            for key in counter_dict:
                if ',' in str(counter_dict[key]):
                    output_str += f'"{counter_dict[key]}",'
                else:
                    output_str += f'{counter_dict[key]},'
            output_str = output_str[:-1]

            if count % FrontEndView.BATCH_SIZE == 0:
                final_str = output_str
                output_str = ''
                yield final_str

        if output_str != '':
            yield output_str

    # get the intervention counts information
    def get_intervention_counts_data(self):
        csv_rows_list = []
        intervention_counts_query = extension_models.DailyInterventionCount.objects.all()
        for counter in intervention_counts_query:
            experiment_member = counter.participant_id
            counter_dict = {
                'participant_id': str(experiment_member.user_id),
                'date': counter.date.strftime('%x'),
                'tld': counter.tld_record.tld if counter.tld_record else '',
                'apply_intervention': counter.tld_record.apply_intervention if counter.tld_record else False,
                'apply_collect_links': counter.tld_record.apply_collect_links if counter.tld_record else False,
                'visit_count': counter.visit_count,
                'intervention_type': counter.intervention_type,
            }
            csv_rows_list += [counter_dict]
        csv_dataframe = pd.DataFrame(csv_rows_list)
        return csv_dataframe.to_csv(index=False)

    # get request the only thing defined
    def get(self, request):
        if self.is_simple_admin(request):
            return self.get_stream_http(self.get_streamed_intervention_count_data, 'intervention_counts_data.csv')
        return redirect('frontend:index')


# Simple Admin Download Visible Records
class SADownloadVisibleLinkRecords(FrontEndView):
    # get streamed information data
    def get_streamed_visible_link_record_data(self):
        labels = [
            'participant_id',
            'parent_url_record',
            'parent_page_url',
            'timestamp',
            'parent_tld',
            'link_url',
            'link_url_tld',
            'js_referrer_url',
            'tagname',
            'is_intersecting',
            'is_visible',
            'visibility_available',
        ]
        output_str = ''
        for elem in labels:
            output_str += f'{elem},'
        output_str = output_str[:-1]
        yield output_str
        output_str = ''

        # count
        count = 0

        visible_links_query = list(extension_models.VisibleLinkRecord.objects.all())
        for visible_link in visible_links_query:
            experiment_member = visible_link.participant_id
            visible_dict = {
                'participant_id': str(experiment_member.user_id),
                'parent_url_record': str(visible_link.parent_page_url_record.record_id),
                'parent_page_url': visible_link.parent_page_url,
                'timestamp': visible_link.visible_timestamp.strftime('%c'),
                'parent_tld': visible_link.parent_tld.tld if visible_link.parent_tld else '',
                'link_url': visible_link.linked_url,
                'link_url_tld': visible_link.linked_tld_url,
                'js_referrer_url': visible_link.referrer_url,
                'tagname': visible_link.tagname,
                'is_intersecting': visible_link.is_intersecting,
                'is_visible': visible_link.is_visible,
                'visibility_available': visible_link.visibility_available,
            }
            output_str += '\n'
            for key in visible_dict:
                if ',' in str(visible_dict[key]):
                    output_str += f'"{visible_dict[key]}",'
                else:
                    output_str += f'{visible_dict[key]},'
            output_str = output_str[:-1]

            if count % FrontEndView.BATCH_SIZE == 0:
                final_str = output_str
                output_str = ''
                yield final_str

        if output_str != '':
            yield output_str

    # get the visible link records downloaded
    def get_visible_link_records(self):
        csv_rows_list = []
        visible_links_query = extension_models.VisibleLinkRecord.objects.all()
        for visible_link in visible_links_query:
            experiment_member = visible_link.participant_id
            visible_dict = {
                'participant_id': str(experiment_member.user_id),
                'parent_url_record': str(visible_link.parent_page_url_record.record_id),
                'parent_page_url': visible_link.parent_page_url,
                'timestamp': visible_link.visible_timestamp.strftime('%c'),
                'parent_tld': visible_link.parent_tld.tld if visible_link.parent_tld else '',
                'link_url': visible_link.linked_url,
                'link_url_tld': visible_link.linked_tld_url,
                'js_referrer_url': visible_link.referrer_url,
                'tagname': visible_link.tagname,
                'is_intersecting': visible_link.is_intersecting,
                'is_visible': visible_link.is_visible,
                'visibility_available': visible_link.visibility_available,
            }
            csv_rows_list += [visible_dict]
        csv_dataframe = pd.DataFrame(csv_rows_list)
        return csv_dataframe.to_csv(index=False)

    # get request the only thing defined
    def get(self, request):
        if self.is_simple_admin(request):
            return self.get_stream_http(self.get_streamed_visible_link_record_data, 'visible_link_records_data.csv')
        return redirect('frontend:index')

# Simple Admin Assign Ad Swap Pairs
class SAAssignPairs(FrontEndView):
    # post request only
    def post(self, request):
        if self.is_simple_admin(request):
            # Get all eligible experiment members
            # Users who:
            # (1) Have onboarded successfully
            # (2) Have not offboarded
            # (3) Are not Intervenr team members
            exp_members = frontend_models.ExperimentMember.objects.filter(has_onboarded=True).filter(offboard_user=False).filter(social_auth__is_staff=False).order_by('?')

            # Get random pairing for all ExperimentMember objects
            n_pairs = math.ceil(len(exp_members) / 2.)
            for pair_i in range(n_pairs):
                em_1 = exp_members[2 * pair_i]
                if (2 * pair_i + 1) == len(exp_members):
                    em_2 = exp_members[0]  # wrap around
                else:
                    em_2 = exp_members[2 * pair_i + 1]
                
                # Set swap_partner
                em_1.swap_partner = em_2
                em_2.swap_partner = em_1
                em_1.save()
                em_2.save()

        return redirect('frontend:simple-admin')


# Simple Admin Reset TLDs
class SAResetTlds(FrontEndView):
    # post request only
    def post(self, request):
        if self.is_simple_admin(request) and 'file_input' in request.FILES:
            try:
                # NOTE: tld_df has to include tld, apply_intervention, apply_collect_links columns
                tld_df = pd.read_csv(request.FILES['file_input'])

                # delete all of the TldRecords that are not in tld_df
                for tld_obj in extension_models.TldRecord.objects.all():
                    if not tld_df['tld'].isin([tld_obj.tld]).any():
                        tld_obj.delete()

                # iter through tld_df and save / make updates from the file
                for index, tld_row in tld_df.iterrows():
                    # Then add on the new TLD records / update the old TLD records
                    if extension_models.TldRecord.objects.filter(tld=tld_row.tld):
                        tld_item = extension_models.TldRecord.objects.get(tld=tld_row.tld)
                        tld_item.apply_intervention = tld_row.apply_intervention
                        tld_item.apply_collect_links = tld_row.apply_collect_links
                        tld_item.save()
                    # Make new TldRecord save
                    else:
                        new_tld = extension_models.TldRecord(
                            tld=tld_row.tld,
                            apply_intervention=tld_row.apply_intervention,
                            apply_collect_links=tld_row.apply_collect_links
                        )
                        new_tld.save()
            except:
                return redirect('frontend:simple-admin')
        return redirect('frontend:simple-admin')


# Simple Admin Reassign Intervention Groups
class SAInterventionGroups(FrontEndView):
    # post request only
    def post(self, request):
        if self.is_simple_admin(request) and 'file_input' in request.FILES:
            try:
                # NOTE: intervention_groups_df has to include user_id, intervention_type
                intervention_groups_df = pd.read_csv(request.FILES['file_input'])
                # iter through intervention groups and save / make updates from the file
                for index, intervention_member_row in intervention_groups_df.iterrows():
                    # Then add on the new TLD records / update the old TLD records
                    if frontend_models.ExperimentMember.objects.filter(user_id=intervention_member_row.user_id):
                        experiment_member = frontend_models.ExperimentMember.objects.get(user_id=intervention_member_row.user_id)
                        experiment_member.intervention_type = intervention_member_row.intervention_type
                        experiment_member.save()
            except:
                return redirect('frontend:simple-admin')
        return redirect('frontend:simple-admin')


# Simple Admin Add Onboarding Codes
class SAOnboardCodes(FrontEndView):
    # post request only
    def post(self, request):
        if self.is_simple_admin(request) and 'file_input' in request.FILES:
            try:
                # NOTE: intervention_groups_df has to include onboard_code
                onboard_codes_df = pd.read_csv(request.FILES['file_input'])
                # iter through intervention groups and save / make updates from the file
                for index, onboard_code_row in onboard_codes_df.iterrows():
                    # Then add on the new TLD records / update the old TLD records
                    if not onboard_models.OnboardCode.objects.filter(onboard_code=onboard_code_row.onboard_code):
                        new_onboard_code = onboard_models.OnboardCode(onboard_code=onboard_code_row.onboard_code)
                        new_onboard_code.save()
            except:
                return redirect('frontend:simple-admin')
        return redirect('frontend:simple-admin')


# Simple Admin Reassign Intervention Groups
class SAOffboardUsers(FrontEndView):
    # post request only
    def post(self, request):
        if self.is_simple_admin(request) and 'file_input' in request.FILES:
            try:
                # NOTE: intervention_groups_df has to include user_id
                offboard_users_df = pd.read_csv(request.FILES['file_input'])

                # iter through intervention groups and save / make updates from the file
                for index, offboard_user_row in offboard_users_df.iterrows():
                    # Then add on the new TLD records / update the old TLD records
                    if frontend_models.ExperimentMember.objects.filter(user_id=offboard_user_row.user_id):
                        experiment_member = frontend_models.ExperimentMember.objects.get(user_id=offboard_user_row.user_id)
                        experiment_member.offboard_user = True
                        experiment_member.offboard_date = datetime.datetime.now()
                        experiment_member.save()
            except:
                return redirect('frontend:simple-admin')
        return redirect('frontend:simple-admin')


# Simple Admin Mass Action work
class SAMassAction(FrontEndView):
    # look at the values on experiment member
    def execute_experiment_member(self, action, experiment_member_list):
        if action == 'offboard-users':
            for experiment_member in experiment_member_list:
                if not experiment_member.offboard_user:
                    experiment_member.offboard_user = True
                    experiment_member.offboard_date = datetime.datetime.now()
                    experiment_member.save()

                    if AUTO_EMAILS_ENABLED:
                        try:
                            html_content = render_to_string('onboard/offboard_email_template.html', {'user_name': experiment_member.social_auth.first_name, 'experiment_type': 'News Media' if experiment_member.experiment_type == frontend_models.ExperimentTypes.NEWS else 'Ads', 'end_date': experiment_member.offboard_date, 'compensation_amount': 15})
                            text_content = strip_tags(html_content)
                            email = EmailMultiAlternatives(
                                f"Thank You for Participating, {experiment_member.social_auth.first_name}!", text_content, settings.EMAIL_HOST_USER, [experiment_member.contact_email],
                            )
                            email.attach_alternative(html_content, 'text/html')
                            email.attach_file('templates/onboard/onboarding_doc.pdf') # Subject to change
                            email.send()
                            print('Offboard Email sent!')
                        except SMTPException as exception:
                            print(f"Couldn't send email to {experiment_member.user_id} because {exception}")
                        except Exception as exception:
                            print(f"Couldn't send email to {experiment_member.user_id} because {exception}")

        elif action == 'delete-users':
            for experiment_member in experiment_member_list:
                experiment_member.delete()
        elif action == 'assign-heavy':
            for experiment_member in experiment_member_list:
                experiment_member.intervention_type = 'heavy'
                experiment_member.save()
        elif action == 'assign-light':
            for experiment_member in experiment_member_list:
                experiment_member.intervention_type = 'light'
                experiment_member.save()
        elif action == 'assign-control':
            for experiment_member in experiment_member_list:
                experiment_member.intervention_type = 'control'
                experiment_member.save()
        elif action == 'allow-onboard-users':
            for experiment_member in experiment_member_list:
                if experiment_member.has_onboard_permission != True: # Prevent sending duplicate email to onboarded participants.
                    experiment_member.has_onboard_permission = True
                    experiment_member.save()

                    if AUTO_EMAILS_ENABLED:
                        try:
                            html_content = render_to_string('onboard/onboard_email_template.html', {'user_name': experiment_member.social_auth.first_name, 'experiment_type': 'News Media' if experiment_member.experiment_type == frontend_models.ExperimentTypes.NEWS else 'Ads', 'start_date': 'N/A', 'end_date': experiment_member.offboard_date, 'onboarding_code': 'N/A', 'compensation_amount': 15})
                            text_content = strip_tags(html_content)
                            email = EmailMultiAlternatives(
                                f"[ACTION-REQUIRED] Congratulations {experiment_member.social_auth.first_name}! You’re Ready to Participate.", text_content, settings.EMAIL_HOST_USER, [experiment_member.contact_email],
                            )
                            email.attach_alternative(html_content, 'text/html')
                            email.attach_file('templates/onboard/onboarding_doc.pdf') # Subject to change
                            email.send()
                            print('Email sent!')
                        except SMTPException as exception:
                            print("Couldn't send email:", exception)
                        except Exception as exception:
                            print("Couldn't send email:", exception)
        elif action == 'assign-news-experiment':
            for experiment_member in experiment_member_list:
                experiment_member.experiment_type = frontend_models.ExperimentTypes.NEWS
                experiment_member.save()
        elif action == 'assign-ads-experiment':
            for experiment_member in experiment_member_list:
                experiment_member.experiment_type = frontend_models.ExperimentTypes.ADS
                experiment_member.save()    

    # execute on the value URL record / Learned a better way now
    def execute_url_record(self, action, url_record_list):
        for url_record in url_record_list:
            if action == 'delete-url-records':
                url_record.delete()

    # execute on the TLD records
    def execute_tld_record(self, action, tld_record_list):
        for tld_obj in tld_record_list:
            if action == 'delete-tld-records':
                tld_obj.delete()
            elif action == 'tld-toggle-intervention':
                tld_obj.apply_intervention = False if tld_obj.apply_intervention else True
                tld_obj.save()
            elif action == 'tld-toggle-collect-links':
                tld_obj.apply_collect_links = False if tld_obj.apply_collect_links else True
                tld_obj.save()

    # execute on the DailyIntervention records
    def execute_intervention_count(self, action, intervention_count_list):
        for intervention_count in intervention_count_list:
            if action == 'delete-intervention-counts':
                intervention_count.delete()

    # execute on VisibleLink records
    def execute_visible_link_record(self, action, visible_link_list):
        for visible_link in visible_link_list:
            if action == 'delete-visible-link-records':
                visible_link.delete()

    # post only
    def post(self, request):
        json_form = forms.SAJsonDataForm(request.POST)
        if self.is_simple_admin(request) and json_form.is_valid():
            json_payload = json_form.cleaned_data['json_data']
            if json_payload['action_data'] == 'experiment-members':
                experiment_member_list = []
                for record in json_payload['records']:
                    experiment_member_list += [frontend_models.ExperimentMember.objects.get(user_id=uuid.UUID(record))]
                self.execute_experiment_member(json_payload['selected_action'], experiment_member_list)
            elif json_payload['action_data'] == 'url-records':
                url_record_list = []
                for record in json_payload['records']:
                    url_record_list += [extension_models.UrlRecord.objects.get(record_id=uuid.UUID(record))]
                self.execute_url_record(json_payload['selected_action'], url_record_list)
            elif json_payload['action_data'] == 'tld-records':
                tld_record_list = []
                for record in json_payload['records']:
                    tld_record_list += [extension_models.TldRecord.objects.get(tld=record)]
                self.execute_tld_record(json_payload['selected_action'], tld_record_list)
            elif json_payload['action_data'] == 'daily-intervention-counts':
                intervention_count_list = []
                for record in json_payload['records']:
                    intervention_count_list += [extension_models.DailyInterventionCount.objects.get(id=record)]
                self.execute_intervention_count(json_payload['selected_action'], intervention_count_list)
            elif json_payload['action_data'] == 'visible-link-records':
                visible_link_record_list = []
                for record in json_payload['records']:
                    visible_link_record_list += [extension_models.VisibleLinkRecord.objects.get(id=record)]
                self.execute_visible_link_record(json_payload['selected_action'], visible_link_record_list)
        return redirect('frontend:simple-admin')


# Intro News Survey
class IntroSurveyNews(FrontEndView):
    def get(self, request):
        context = {}
        form = forms.IntroSurveyFormNews()
        context["show_prev_step"] = True
        context['form_url'] = {'previous': 'onboard:demographics_prolific'}

        # Check if user has already completed form
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        if experiment_member is None:
            return render(request, 'frontend/start.html', context)
        context['experiment_type'] = 'News Media'
        if frontend_models.IntroSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_ALERT'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.IntroSurvey.objects.get(user_id=experiment_member).response_json
            form = forms.IntroSurveyFormNews(initial=response)
            form = self.disable_fields(form)
            context["form"] = form
            return render(request, 'frontend/intro_survey.html', context)

        # Otherwise, render new form
        context["form"] = form
        return render(request, 'frontend/intro_survey.html', context)

    def post(self, request):
        form = forms.IntroSurveyFormNews(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context = {}
        context['experiment_member'] = experiment_member
        if experiment_member:
            # If user already has submitted form, ignore and direct to next step
            if frontend_models.IntroSurvey.objects.filter(user_id=experiment_member):
                #return redirect("onboard:extension")
                return redirect("onboard:install")

            elif form.is_valid():
                # Process form entries into JSON to save to model
                # Save submission to IntroSurvey model
                response = form.cleaned_data
                new_survey_record = frontend_models.IntroSurvey(
                    user_id=experiment_member,
                    response_json=response,
                )
                new_survey_record.save()
                experiment_member.onboard_survey = True
                experiment_member.save()

                # return redirect('onboard:extension')
                return redirect("onboard:install")
        else:
            form = forms.IntroSurveyFormNews()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/intro_survey.html', context)


# Intro Ads Survey
class IntroSurvey(FrontEndView):
    def get(self, request):
        context = {}
        form = forms.IntroSurveyForm()
        context["show_prev_step"] = True
        context['form_url'] = {'previous': 'onboard:start_onboard'}

        # Check if user has already completed form
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        if frontend_models.IntroSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_ALERT'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.IntroSurvey.objects.get(user_id=experiment_member).response_json
            form = forms.IntroSurveyForm(initial=response)
            form = self.disable_fields(form)
            context["form"] = form
            return render(request, 'frontend/intro_survey.html', context)

        # Otherwise, render new form
        context["form"] = form
        return render(request, 'frontend/intro_survey.html', context)
    
    def post(self, request):
        form = forms.IntroSurveyForm(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context = {}
        context['experiment_member'] = experiment_member
        if experiment_member:
            # If user already has submitted form, ignore and direct to next step
            if frontend_models.IntroSurvey.objects.filter(user_id=experiment_member):
                return redirect("onboard:extension")
            
            elif form.is_valid():
                # Process form entries into JSON to save to model
                # Save submission to IntroSurvey model
                response = form.cleaned_data
                new_survey_record = frontend_models.IntroSurvey(
                    user_id = experiment_member,
                    response_json = response,
                )
                new_survey_record.save()
                experiment_member.onboard_survey = True
                experiment_member.save()
                
                return redirect('onboard:extension')
        else:
            form = forms.IntroSurveyForm()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/intro_survey.html', context)

# Midpoint News Survey
class MidpointSurveyNews(FrontEndView):
    def is_eligible(self, experiment_member):
        is_eligible = True
        return is_eligible

    def get(self, request):
        context = {}
        experimentmember_param = request.GET.get('experimentmember')
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        if experiment_member is None:
            # Direct to log in again
            return render(request, 'frontend/start.html', context)
        else:
            if (experimentmember_param is not None) and (experiment_member.social_auth.is_staff):
                # Fetch information for provided experiment member
                experiment_member = frontend_models.ExperimentMember.objects.get(user_id=experimentmember_param, experiment_type=CURRENT_EXPERIMENT)

        is_eligible = self.is_eligible(experiment_member)

        if not is_eligible:
            context["SURVEY_ALERT"] = "You do not have a sufficient number of collected URLs to complete this survey and should have received an email about early offboarding for your participation so far. Please contact the Intervenr Team if you need additional assistance."
        else:
            # News form
            form_news = forms.MidpointSurveyFormNews()

        # Check if user has already completed form
        if frontend_models.MidpointSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_WARN'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.MidpointSurvey.objects.get(user_id=experiment_member).response_json

            form_news = forms.MidpointSurveyFormNews(initial=response)
            form_news = self.disable_fields(form_news)
            context["form_news"] = form_news
            context["block_next_step"] = True
            return render(request, 'frontend/midpoint_survey_news.html', context)

        # Otherwise, render new form
        if 'SURVEY_ALERT' not in context:
            context["form_news"] = form_news
            context["sections"] = ["Perceptions of algorithmic bias", "Ad sentiment", "Study experience"]
            context["descriptions"] = [
                "Please answer the following questions about the sample of ads displayed below.",
                "In this section, please answer a brief set of questions related to your sentiment for each displayed ad.",
                "Please answer a final set of questions about your experience in this study.",
            ]
        return render(request, 'frontend/midpoint_survey_news.html', context)

    def post(self, request):
        context = {}
        response = dict(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        # Process form entries into JSON to save to model
        if experiment_member:
            # Save submission to MidpointSurvey model
            new_survey_record = frontend_models.MidpointSurvey(
                user_id=experiment_member,
                response_json=response,
            )
            new_survey_record.save()
            experiment_member.middle_survey = True
            experiment_member.save()

            context["completion_message"] = "Thank you for completing the midpoint survey! You're now all set to continue on in the study."
            context['link'] = 'frontend:index'
            context['completion_link_message'] = 'Go Back to Home Page'
            return render(request, 'frontend/midpoint_survey_complete.html', context)
        else:
            form = forms.MidpointSurveyFormNews()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/midpoint_survey.html', context)


# Midpoint News Survey
class SecondMidpointSurveyNews(FrontEndView):
    def is_eligible(self, experiment_member):
        is_eligible = False
        user_threshold_time = experiment_member.onboard_date.date() + datetime.timedelta(days=12)
        midpointSurveyCompleted = True if frontend_models.MidpointSurvey.objects.filter(user_id=experiment_member) else False
        if user_threshold_time <= datetime.date.today() and midpointSurveyCompleted:
            is_eligible = True
        return is_eligible

    def get(self, request):
        context = {}
        experimentmember_param = request.GET.get('experimentmember')
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        if experiment_member is None:
            # Direct to log in again
            return render(request, 'frontend/start.html', context)
        else:
            if (experimentmember_param is not None) and (experiment_member.social_auth.is_staff):
                # Fetch information for provided experiment member
                experiment_member = frontend_models.ExperimentMember.objects.get(user_id=experimentmember_param, experiment_type=CURRENT_EXPERIMENT)

        is_eligible = self.is_eligible(experiment_member)

        if not is_eligible:
            context["SURVEY_ALERT"] = "You are not yet eligible to take the checkin survey."
        else:
            # News form
            form_news = forms.SecondMidpointSurveyFormNews()

        # Check if user has already completed form
        if frontend_models.SecondMidpointSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_WARN'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.SecondMidpointSurvey.objects.get(user_id=experiment_member).response_json

            form_news = forms.SecondMidpointSurveyFormNews(initial=response)
            form_news = self.disable_fields(form_news)
            context["form_news"] = form_news
            context["block_next_step"] = True
            return render(request, 'frontend/second_midpoint_survey_news.html', context)

        # Otherwise, render new form
        if 'SURVEY_ALERT' not in context:
            context["form_news"] = form_news
            context["sections"] = ["Perceptions of algorithmic bias", "Ad sentiment", "Study experience"]
            context["descriptions"] = [
                "Please answer the following questions about the sample of ads displayed below.",
                "In this section, please answer a brief set of questions related to your sentiment for each displayed ad.",
                "Please answer a final set of questions about your experience in this study.",
            ]
        return render(request, 'frontend/second_midpoint_survey_news.html', context)

    def post(self, request):
        context = {}
        response = dict(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        # Process form entries into JSON to save to model
        if experiment_member:
            # Save submission to MidpointSurvey model
            new_survey_record = frontend_models.SecondMidpointSurvey(
                user_id=experiment_member,
                response_json=response,
            )
            new_survey_record.save()
            experiment_member.second_middle_survey = True
            # Swap their Twitter intervention
            if experiment_member.intervention_type == 'for you':
                experiment_member.intervention_type = 'following'
            else:
                experiment_member.intervention_type = 'for you'
            experiment_member.save()

            context["completion_message"] = "Thank you for completing the checkin survey! You're now all set to continue on in the study."
            context['link'] = 'frontend:index'
            context['completion_link_message'] = 'Go Back to Home Page'
            return render(request, 'frontend/second_midpoint_survey_complete.html', context)
        else:
            form = forms.SecondMidpointSurveyFormNews()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/second_midpoint_survey.html', context)


# Final News Survey
class FinalSurveyNews(FrontEndView):
    def is_eligible(self, experiment_member):
        is_eligible = True
        return is_eligible

    def get(self, request):
        context = {}
        experimentmember_param = request.GET.get('experimentmember')
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        if experiment_member is None:
            # Direct to log in again
            return render(request, 'frontend/start.html', context)
        else:
            if (experimentmember_param is not None) and (experiment_member.social_auth.is_staff):
                # Fetch information for provided experiment member
                experiment_member = frontend_models.ExperimentMember.objects.get(user_id=experimentmember_param, experiment_type=CURRENT_EXPERIMENT)

        is_eligible = self.is_eligible(experiment_member)

        if not is_eligible:
            context["SURVEY_ALERT"] = "You do not have a sufficient number of collected URLs to complete this survey and should have received an email about early offboarding for your participation so far. Please contact the Intervenr Team if you need additional assistance."
            # context["SURVEY_ALERT"] = "The time period for the final survey has ended and additional responses are not being accepted. Please contact the Intervenr Team if you need additional assistance."
        else:
            form_news = forms.FinalSurveyFormNews()

        # Check if user has already completed form
        if frontend_models.FinalSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_WARN'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.FinalSurvey.objects.get(user_id=experiment_member).response_json

            form_news = forms.FinalSurveyFormNews(initial=response)
            form_news = self.disable_fields(form_news)

            context["form_news"] = form_news
            context["block_next_step"] = True
            return render(request, 'frontend/final_survey_news.html', context)

        # Otherwise, render new form
        if 'SURVEY_ALERT' not in context:
            context["form_news"] = form_news
        return render(request, 'frontend/final_survey_news.html', context)

    def post(self, request):
        context = {}
        response = dict(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        # Process form entries into JSON to save to model
        if experiment_member:
            # Save submission to FinalSurvey model
            new_survey_record = frontend_models.FinalSurvey(
                user_id=experiment_member,
                response_json=response,
            )
            new_survey_record.save()
            experiment_member.offboard_survey = True
            experiment_member.save()

            context[
                "completion_message"] = "Thank you for completing the final survey! You're now all set to receive your compensation; look out to an email from us in the next few days."
            context['link'] = 'frontend:index'
            context['completion_link_message'] = 'Go Back to Home Page'
            return render(request, 'frontend/final_survey_complete.html', context)
        else:
            form = forms.FinalSurveyNewsForm()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/final_survey_news.html', context)


# Midpoint Ads Survey
class MidpointSurvey(FrontEndView):
    def is_eligible(self, experiment_member, n_sample=4, n_holistic=40):
        _, _, is_eligible = self.get_ad_sets(experiment_member, n_sample, n_holistic)
        return is_eligible

    def get_person_ad_ids(self, participant_id):
        # Sample ads for the participant that contain people (based on offline object detection)
        person_ad_ids = ads_extension_models.AdMetadata.objects.filter(participant_id=participant_id).filter(data_type="person").values_list('ad_record_id', flat=True)
        return person_ad_ids

    def sample_ads(self, participant_id, n, person_ad_ids=None, seen=None, people=None):
        ad_ids = None
        ad_ids = ads_extension_models.AdRecord.objects.filter(participant_id = participant_id).filter(intervenr_ad_type=ads_extension_models.IntervenrAdTypes.OBS).filter(img_was_downloaded=FILT_TO_DOWNLOADED)
        
        # Filter based on whether ads were seen or not
        # (Don't filter if seen=None)
        if seen is True:
            # Seen ads
            ad_ids = ad_ids.filter(view_count__gt=0)
        elif seen is False:
            # Unseen ads
            ad_ids = ad_ids.filter(view_count=0)
        
        # Futher filter depending on whether ads should contain people or not
        # (Don't filter if people=None)
        if people is True:
            ad_ids = ad_ids.filter(record_id__in=person_ad_ids)
        elif people is False:
            ad_ids = ad_ids.exclude(record_id__in=person_ad_ids)
        
        ad_ids = ad_ids.values_list('record_id', flat=True)

        # Sample the final ads from the eligible set
        if ad_ids is not None:
            ad_ids = list(ad_ids)
            if len(ad_ids) >= n:
                sampled_ids = random.sample(ad_ids, n)
                ads = ads_extension_models.AdRecord.objects.filter(record_id__in=sampled_ids)
                return ads
            elif len(ad_ids) > 0:
                ads = ads_extension_models.AdRecord.objects.filter(record_id__in=ad_ids)
                return ads
        return None
    
    def get_ad_sets(self, experiment_member, n_sample, n_holistic):
        is_eligible = True
        participant_id = experiment_member.user_id
        swapPartner_id = experiment_member.swap_partner.user_id

        # HOLISTIC 
        holistic_ads = self.sample_ads(participant_id, n=n_holistic, seen=True)
        if (len(holistic_ads) == 0):
            is_eligible = False
            return None, holistic_ads, is_eligible

        # PER-AD section
        person_ad_ids = self.get_person_ad_ids(participant_id)
        swap_person_ad_ids = self.get_person_ad_ids(swapPartner_id)
        ad_sets = {
            "user_seen_people": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=True, people=True
            ), 
            "user_seen_noPeople": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=True, people=False
            ),
            "user_unseen_people": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=False, people=True
            ), 
            "user_unseen_noPeople": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=False, people=False
            ), 
            "other_people": self.sample_ads(
                swapPartner_id, person_ad_ids=swap_person_ad_ids, n=n_sample, 
                people=True
            ),
            "other_noPeople": self.sample_ads(
                swapPartner_id, person_ad_ids=swap_person_ad_ids, n=n_sample, 
                people=False
            ),
            "attn_check": [None],
        }
        no_user_seen = (ad_sets["user_seen_people"] is None) and (ad_sets["user_seen_noPeople"] is None)
        no_user_unseen = (ad_sets["user_unseen_people"] is None) and (ad_sets["user_unseen_noPeople"] is None)
        no_other = (ad_sets["other_people"] is None) and (ad_sets["other_noPeople"] is None)
        if no_user_seen or no_user_unseen or no_other:
            is_eligible = False
            return ad_sets, holistic_ads, is_eligible

        return ad_sets, holistic_ads, is_eligible

    def get(self, request):
        context = {}
        experimentmember_param = request.GET.get('experimentmember')
        experiment_member = self.get_experiment_member_or_none(request)
        if experiment_member is None:
            # Direct to log in again
            return render(request, 'frontend/start.html', context)
        else:
            if (experimentmember_param is not None) and (experiment_member.social_auth.is_staff):
                # Fetch information for provided experiment member
                experiment_member = frontend_models.ExperimentMember.objects.get(user_id=experimentmember_param)

        # Fetch per-ad and holistic ad sets
        n_sample = 4
        n_holistic = 40
        exp_member_str = str(experiment_member.user_id)
        # if exp_member_str in cached_sampled_ads:
        #     ad_sets_ids = cached_sampled_ads[exp_member_str]["per_ad"]
        #     ad_sets = {
        #         k: ads_extension_models.AdRecord.objects.filter(record_id__in=cur_ids) if k != "attn_check" else [None] for k, cur_ids in ad_sets_ids.items()
        #     }
            
        #     holistic_ads_ids = cached_sampled_ads[exp_member_str]["holistic"]
        #     holistic_ads = ads_extension_models.AdRecord.objects.filter(record_id__in=holistic_ads_ids)
        #     is_eligible = True
        # elif experiment_member.contact_email == settings.TEST_ACCOUNT_EMAIL:
        #     # TEMP to test
        #     exp_member_str = '053f656e-7365-4274-9c32-266d42ddaa5a'
        #     ad_sets_ids = cached_sampled_ads[exp_member_str]["per_ad"]
        #     ad_sets = {
        #         k: ads_extension_models.AdRecord.objects.filter(record_id__in=cur_ids) if k != "attn_check" else [None] for k, cur_ids in ad_sets_ids.items()
        #     }
            
        #     holistic_ads_ids = cached_sampled_ads[exp_member_str]["holistic"]
        #     holistic_ads = ads_extension_models.AdRecord.objects.filter(record_id__in=holistic_ads_ids)
        #     is_eligible = True
        # else:
        #     is_eligible = False

        is_eligible = False

        if not is_eligible:
            # context["SURVEY_ALERT"] = "You do not have a sufficient number of collected ads to complete this survey and should have received an email about early offboarding for your participation so far. Please contact the Intervenr Team if you need additional assistance."
            context["SURVEY_ALERT"] = "The time period for the midpoint survey has ended and additional responses are not being accepted. Please contact the Intervenr Team if you need additional assistance."
        else:
            # PER-AD form
            n_sample_total = sum([len(ad_set) for ad_set in ad_sets.values() if ad_set is not None])
            form_ads_sample = forms.MidpointSurveyAdsSampleForm(ad_sets=ad_sets)

            # HOLISTIC form
            ad_record_ids = [ad.record_id for ad in holistic_ads]
            holistic_ad_urls = [forms.create_presigned_url(ad) for ad in holistic_ads]
            form_ads_holistic = forms.MidpointSurveyAdsHolisticForm(ad_record_ids)
        
        # Check if user has already completed form
        if frontend_models.MidpointSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_WARN'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.MidpointSurvey.objects.get(user_id=experiment_member).response_json

            form_ads_sample = forms.MidpointSurveyAdsSampleForm(initial=response, n_max=n_sample)
            form_ads_sample = self.disable_fields(form_ads_sample)
            form_study_exp = forms.MidpointSurveyExperienceForm(initial=response)
            form_study_exp = self.disable_fields(form_study_exp)
            form_ads_holistic = forms.MidpointSurveyAdsHolisticForm(initial=response)
            form_ads_holistic = self.disable_fields(form_ads_holistic)

            context["form_ads_holistic"] = form_ads_holistic
            context["form_ads_sample"] = form_ads_sample
            context["form_study_exp"] = form_study_exp
            context["block_next_step"] = True
            return render(request, 'frontend/midpoint_survey.html', context)

        # Otherwise, render new form
        if 'SURVEY_ALERT' not in context:
            context["form_ads_holistic"] = form_ads_holistic
            context["form_ads_sample"] = form_ads_sample
            context["form_study_exp"] = forms.MidpointSurveyExperienceForm()
            context["form_ads_sample_inds"] = list(range(1, n_sample_total + 1))
            context["holistic_ad_urls"] = holistic_ad_urls
            context["sections"] = ["Ad overview", "Ad sentiment", "Study experience"]
            context["descriptions"] = [
                "Please answer the following questions about the sample of ads displayed below.",
                "In this section, please answer a brief set of questions related to your sentiment for each displayed ad.",
                "Please answer a final set of questions about your experience in this study.",
            ]
        return render(request, 'frontend/midpoint_survey.html', context)
    
    def post(self, request):
        context = {}
        response = dict(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        # Process form entries into JSON to save to model
        if experiment_member:
            # Save submission to MidpointSurvey model
            new_survey_record = frontend_models.MidpointSurvey(
                user_id = experiment_member,
                response_json = response,
            )
            new_survey_record.save()
            experiment_member.middle_survey = True
            experiment_member.save()
            
            context["completion_message"] = "Thank you for completing the midpoint survey! You're now all set to continue on in the study."
            context['link'] = 'frontend:index'
            context['completion_link_message'] = 'Go Back to Home Page'
            return render(request, 'frontend/midpoint_survey_complete.html', context)
        else:
            form = forms.IntroSurveyForm()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/midpoint_survey.html', context)


# Final Ads Survey
class FinalSurvey(FrontEndView):
    def is_eligible(self, experiment_member, n_sample=4, n_holistic=40):
        _, _, is_eligible = self.get_ad_sets(experiment_member, n_sample, n_holistic)
        return is_eligible

    def get_person_ad_ids(self, participant_id):
        # Sample ads for the participant that contain people (based on offline object detection)
        person_ad_ids = ads_extension_models.AdMetadata.objects.filter(participant_id=participant_id).filter(data_type="person").values_list('ad_record_id', flat=True)
        return person_ad_ids

    # def sample_ads(self, participant_id, n, exclude=False, seen=False):
    def sample_ads(self, participant_id, n, person_ad_ids=None, seen=None, people=None, other=False):
        ad_ids = None
        if other:
            # User's original (unseen) ads
            ad_ids = ads_extension_models.AdRecord.objects.filter(participant_id = participant_id).filter(intervenr_ad_type=ads_extension_models.IntervenrAdTypes.INTERV_ORIG).filter(img_was_downloaded=FILT_TO_DOWNLOADED)
        else:
            # Users' intervention phase (swapped-in) ads   
            ad_ids = ads_extension_models.AdRecord.objects.filter(participant_id = participant_id).filter(intervenr_ad_type=ads_extension_models.IntervenrAdTypes.INTERV_SWAP).filter(img_was_downloaded=FILT_TO_DOWNLOADED)

            # Filter based on whether ads were seen or not
            # (Don't filter if seen=None)
            if seen:
                # Seen ads
                # Get unique original ad IDs
                orig_ad_ids = ad_ids.filter(view_count__gt=0).values_list('original_ad_id', flat=True)
                orig_ad_ids = set(orig_ad_ids)
                # Sample n original ad IDs
                # sampled_orig_ad_ids = random.sample(orig_ad_ids, min(n, len(orig_ad_ids)))
                # Restrict ad_pk sample to this set of original ad IDs
                ad_ids = ad_ids.filter(original_ad_id__in=orig_ad_ids).filter(view_count__gt=0)
                
            else:
                # Unseen ads
                # Get unique original ad IDs
                orig_ad_ids = ad_ids.filter(view_count=0).values_list('original_ad_id', flat=True)
                orig_ad_ids_seen = ad_ids.filter(view_count__gt=0).values_list('original_ad_id', flat=True)
                # Ensure unseen ads haven't been seen in another instance
                orig_ad_ids = set(orig_ad_ids)
                orig_ad_ids_seen = set(orig_ad_ids_seen)
                orig_ad_ids = orig_ad_ids - orig_ad_ids_seen
                # Sample n original ad IDs
                # sampled_orig_ad_ids = random.sample(orig_ad_ids, min(n, len(orig_ad_ids)))
                # Restrict ad_pk sample to this set of original ad IDs
                ad_ids = ad_ids.filter(original_ad_id__in=orig_ad_ids).filter(view_count=0)
            
        # Futher filter depending on whether ads should contain people or not
        # (Don't filter if people=None)
        if people is True:
            ad_ids = ad_ids.filter(record_id__in=person_ad_ids)
        elif people is False:
            ad_ids = ad_ids.exclude(record_id__in=person_ad_ids)
        
        ad_ids = ad_ids.values_list('record_id', flat=True)

        # Sample the final ads from the eligible set
        if ad_ids is not None:
            ad_ids = list(ad_ids)
            if len(ad_ids) >= n:
                sampled_ids = random.sample(ad_ids, n)
                ads = ads_extension_models.AdRecord.objects.filter(record_id__in=sampled_ids)
                return ads
            elif len(ad_ids) > 0:
                ads = ads_extension_models.AdRecord.objects.filter(record_id__in=ad_ids)
                return ads
        return None

    def get_ad_sets(self, experiment_member, n_sample, n_holistic):
        is_eligible = True
        participant_id = experiment_member.user_id

        # HOLISTIC 
        holistic_ads = self.sample_ads(participant_id, n=n_holistic, seen=True)
        if (len(holistic_ads) == 0):
            is_eligible = False
            return None, holistic_ads, is_eligible

        # PER-AD section
        person_ad_ids = self.get_person_ad_ids(participant_id)
        ad_sets = {
            "user_seen_people": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=True, people=True
            ), 
            "user_seen_noPeople": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=True, people=False
            ),
            "user_unseen_people": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=False, people=True
            ), 
            "user_unseen_noPeople": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                seen=False, people=False
            ), 
            "other_people": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                people=True, other=True
            ),
            "other_noPeople": self.sample_ads(
                participant_id, person_ad_ids=person_ad_ids, n=n_sample, 
                people=False, other=True
            ),
            "attn_check": [None],
        }
        no_user_seen = (ad_sets["user_seen_people"] is None) and (ad_sets["user_seen_noPeople"] is None)
        no_user_unseen = (ad_sets["user_unseen_people"] is None) and (ad_sets["user_unseen_noPeople"] is None)
        no_other = (ad_sets["other_people"] is None) and (ad_sets["other_noPeople"] is None)
        if no_user_seen or no_user_unseen or no_other:
            is_eligible = False
            return ad_sets, holistic_ads, is_eligible

        return ad_sets, holistic_ads, is_eligible

    def get(self, request):
        context = {}
        experimentmember_param = request.GET.get('experimentmember')
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        if experiment_member is None:
            # Direct to log in again
            return render(request, 'frontend/start.html', context)
        else:
            if (experimentmember_param is not None) and (experiment_member.social_auth.is_staff):
                # Fetch information for provided experiment member
                experiment_member = frontend_models.ExperimentMember.objects.get(user_id=experimentmember_param)

        # Fetch per-ad and holistic ad sets
        n_sample = 4
        n_holistic = 40
        exp_member_str = str(experiment_member.user_id)
        # if exp_member_str in cached_final_sampled_ads:
        #     ad_sets_ids = cached_final_sampled_ads[exp_member_str]["per_ad"]
        #     ad_sets = {
        #         k: ads_extension_models.AdRecord.objects.filter(record_id__in=cur_ids) if k != "attn_check" else [None] for k, cur_ids in ad_sets_ids.items()
        #     }
            
        #     holistic_ads_ids = cached_final_sampled_ads[exp_member_str]["holistic"]
        #     holistic_ads = ads_extension_models.AdRecord.objects.filter(record_id__in=holistic_ads_ids)
        #     is_eligible = True
        # elif experiment_member.contact_email == settings.TEST_ACCOUNT_EMAIL:
        #     # TEMP to test
        #     exp_member_str = '0500a2e2-41ab-4066-9f57-6652c12d2a28'
        #     ad_sets_ids = cached_final_sampled_ads[exp_member_str]["per_ad"]
        #     ad_sets = {
        #         k: ads_extension_models.AdRecord.objects.filter(record_id__in=cur_ids) if k != "attn_check" else [None] for k, cur_ids in ad_sets_ids.items()
        #     }
            
        #     holistic_ads_ids = cached_final_sampled_ads[exp_member_str]["holistic"]
        #     holistic_ads = ads_extension_models.AdRecord.objects.filter(record_id__in=holistic_ads_ids)
        #     is_eligible = True
        # else:
        #     is_eligible = False
        is_eligible = False

        if not is_eligible:
            # context["SURVEY_ALERT"] = "You do not have a sufficient number of collected ads to complete this survey and should have received an email about early offboarding for your participation so far. Please contact the Intervenr Team if you need additional assistance."
            context["SURVEY_ALERT"] = "The time period for the final survey has ended and additional responses are not being accepted. Please contact the Intervenr Team if you need additional assistance."
        else:
            # PER-AD form
            n_sample_total = sum([len(ad_set) for ad_set in ad_sets.values() if ad_set is not None])
            form_ads_sample = forms.FinalSurveyAdsSampleForm(ad_sets=ad_sets)

            # HOLISTIC form
            ad_record_ids = [ad.record_id for ad in holistic_ads]
            holistic_ad_urls = [forms.create_presigned_url(ad) for ad in holistic_ads]
            form_ads_holistic = forms.FinalSurveyAdsHolisticForm(ad_record_ids)
        
        # Check if user has already completed form
        if frontend_models.FinalSurvey.objects.filter(user_id=experiment_member):
            context['SURVEY_WARN'] = 'You have already completed this form and cannot edit your response. Please continue or contact the Intervenr Team if you need to edit your response.'
            response = frontend_models.FinalSurvey.objects.get(user_id=experiment_member).response_json

            form_ads_sample = forms.FinalSurveyAdsSampleForm(initial=response, n_max=n_sample)
            form_ads_sample = self.disable_fields(form_ads_sample)
            form_study_exp = forms.FinalSurveyExperienceForm(initial=response)
            form_study_exp = self.disable_fields(form_study_exp)
            form_ads_holistic = forms.MidpointSurveyAdsHolisticForm(initial=response)
            form_ads_holistic = self.disable_fields(form_ads_holistic)

            context["form_ads_holistic"] = form_ads_holistic
            context["form_ads_sample"] = form_ads_sample
            context["form_study_exp"] = form_study_exp
            context["block_next_step"] = True
            return render(request, 'frontend/final_survey.html', context)

        # Otherwise, render new form
        if 'SURVEY_ALERT' not in context:
            context["form_ads_holistic"] = form_ads_holistic
            context["form_ads_sample"] = form_ads_sample
            context["form_study_exp"] = forms.FinalSurveyExperienceForm()
            context["form_ads_sample_inds"] = list(range(1, n_sample_total + 1))
            context["holistic_ad_urls"] = holistic_ad_urls
            context["sections"] = ["Ad overview", "Ad sentiment", "Study experience"]
            context["descriptions"] = [
                "Please answer the following questions about the sample of ads displayed below.",
                "In this section, please answer a brief set of questions related to your sentiment for each displayed ad.",
                "Please answer a final set of questions about your experience in this study.",
            ]
        return render(request, 'frontend/final_survey.html', context)
    
    def post(self, request):
        context = {}
        response = dict(request.POST)
        experiment_member = self.get_experiment_member_or_none(request)
        context['experiment_member'] = experiment_member
        # Process form entries into JSON to save to model
        if experiment_member:
            # Save submission to FinalSurvey model
            new_survey_record = frontend_models.FinalSurvey(
                user_id = experiment_member,
                response_json = response,
            )
            new_survey_record.save()
            experiment_member.offboard_survey = True
            experiment_member.save()
            
            context["completion_message"] = "Thank you for completing the final survey! You're now all set to receive your compensation; look out to an email from us in the next few days."
            context['link'] = 'frontend:index'
            context['completion_link_message'] = 'Go Back to Home Page'
            return render(request, 'frontend/final_survey_complete.html', context)
        else:
            form = forms.IntroSurveyForm()
            context['form'] = form
            context["SURVEY_ALERT"] = "Sorry, there was an error in your form submission. Please try to complete the survey again or contact the Intervenr Team if you need help."
            return render(request, 'frontend/final_survey.html', context)


# Dashboard bulk action - Offboarding users
class MassOffboardUsers(FrontEndView):
    # post request only
    def post(self, request):
        input_emails = request.POST['input_emails'].replace(" ","").split(',')
        try:
            experiment_members = frontend_models.ExperimentMember.objects.filter(contact_email__in=input_emails)
            for exp_mem in experiment_members:
                exp_mem.offboard_user = True
                exp_mem.offboard_date = datetime.datetime.now()
                exp_mem.save()
            return redirect('frontend:dashboard')
        except Exception as error:
            print(error)
            

# Dashboard bulk action - Granting permission to onboard
class GrantOnboardPermission(FrontEndView):
    # post request only
    def post(self, request):
        input_emails = request.POST['input_emails'].replace(" ","").split(',')
        try:
            experiment_members = frontend_models.ExperimentMember.objects.filter(contact_email__in=input_emails)
            for exp_mem in experiment_members:
                exp_mem.has_onboard_permission = True
                exp_mem.save()
            return redirect('frontend:dashboard')
        except Exception as error:
            print(error)


# Dashboard bulk action - Revoking permission to onboard
class RevokeOnboardPermission(FrontEndView):
    # post request only
    def post(self, request):
        not_onboarded_exp_mems = frontend_models.ExperimentMember.objects.filter(has_onboarded=False)
        for not_onboarded_exp_mem in not_onboarded_exp_mems:
            not_onboarded_exp_mem.has_onboard_permission = False
            not_onboarded_exp_mem.save()
        return redirect('frontend:dashboard')


# Start Page
def start(request):
    context = {}
    if request.user.is_authenticated:
        context['experiment_member'] = frontend_models.ExperimentMember.objects.filter(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT).first()
    if 'LOGIN_ERROR' in request.session:
        context['LOGIN_ERROR'] = request.session['LOGIN_ERROR']
        del request.session['LOGIN_ERROR']
    return render(request, 'frontend/start.html', context)


# Privacy Page
def privacy(request):
    context = {}
    if request.user.is_authenticated:
        context['experiment_member'] = frontend_models.ExperimentMember.objects.filter(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT).first()
    return render(request, 'frontend/privacy.html', context)


# About Page
def about(request):
    context = {}
    if request.user.is_authenticated:
        context['experiment_member'] = frontend_models.ExperimentMember.objects.filter(social_auth=request.user, experiment_type=CURRENT_EXPERIMENT).first()
    return render(request, 'frontend/about.html', context)


# Logout Page
def logout_view(request):
    logout(request)
    return redirect('frontend:index')
