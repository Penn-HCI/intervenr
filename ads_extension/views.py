from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from frontend.models import ExperimentMember, ExperimentSettings
from ads_extension import models
import json
import uuid
import logging
from django.shortcuts import render
from django.db.models import F
import requests
import datetime
import random

PAUSE_STUDY = True # Lever to pause all study ad collection/swapping

# Logger to assist in live debugging
logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class QualtricsView(View):
    def post(self, request):
        # TODO: populate with future Qualtrics survey data
        return JsonResponse({'success': True})

@method_decorator(csrf_exempt, name='dispatch')
class ExtensionView(View):
    def is_valid_experiment_member(self, request):
        data = json.loads(request.body)
        uuid_value = data['ParticipantId']
        uuid_obj = uuid.UUID(uuid_value)
        has_valid_exp_member = bool(ExperimentMember.objects.filter(user_id=uuid_obj).count())
        if has_valid_exp_member:
            # Return whether user is still in experiment (not offboarded)
            return (not self.get_experiment_member(data).offboard_user)
        else:
            return False

    def get_experiment_member(self, data):
        uuid_value = data['ParticipantId']
        uuid_obj = uuid.UUID(uuid_value)
        return ExperimentMember.objects.get(user_id=uuid_obj)

    def get_intervenr_ad_type(self):
        # [obs_start, obs_end) = observational phase
        # [interv_start, interv_end) = intervention phase
        # any other date ranges = mark to ignore

        # Set ad type based on experimental phase
        cur_exp = ExperimentSettings.objects.all().order_by("-creation_date").first()

        if cur_exp is None:
            # No experiment has been created
            return models.IntervenrAdTypes.TO_IGNORE

        cur_date = datetime.date.today()
        if (cur_date >= cur_exp.obs_start) and (cur_date < cur_exp.obs_end):
            # Observational phase
            return models.IntervenrAdTypes.OBS
        elif (cur_date >= cur_exp.interv_start) and (cur_date < cur_exp.interv_end):
            # Intervention phase
            return models.IntervenrAdTypes.INTERV_ORIG
        else:
            # Neither phase; save, but don't store as part of these phases
            return models.IntervenrAdTypes.TO_IGNORE

    def log(self, request=None, data=None, message="NA"):
        if data:
            new_log = models.ExtensionError(request_json=data, message=message)
            new_log.save()
        elif request:
            data = json.loads(request.body)
            new_log = models.ExtensionError(request_json=data, message=message)
            new_log.save()
        logger.error(message)
        logger.debug(data)

    def get_prev_tab_or_none(self, data):
        if data['prevTabId']:
            return data['prevTabId']
        else:
            return None

# View to implement interventions
class ActionView(ExtensionView):
    def post(self, request, debug=False):
        if PAUSE_STUDY:
            return JsonResponse({})

        if not self.is_valid_experiment_member(request):
            # Not valid experiment member; don't provide swapped ad
            return JsonResponse({})

        cur_ad_type = self.get_intervenr_ad_type()

        # TEMP
        data = json.loads(request.body)
        cur_exp_member = self.get_experiment_member(data)
        if settings.TEST_ACCOUNT_EMAIL and cur_exp_member.contact_email == settings.TEST_ACCOUNT_EMAIL:
            cur_ad_type = models.IntervenrAdTypes.INTERV_ORIG

        if cur_ad_type != models.IntervenrAdTypes.INTERV_ORIG:
            # Not intervention phase; don't provide swapped ad
            return JsonResponse({})

        # data = json.loads(request.body)
        # cur_exp_member = self.get_experiment_member(data)
        orig_ad = data["orig_ad"]

        # Get original ad dimensions
        content_type = orig_ad["contentType"]
        if content_type == "img":
            orig_w = orig_ad["contentData"]["width"]
            orig_h = orig_ad["contentData"]["height"]
            orig_dim = "wide" if orig_w > orig_h else "tall"
        else:
            return JsonResponse({})  # Don't provide swapped ad

        # Query from swap partner's observational phase ads
        partner_exp_member = cur_exp_member.swap_partner
        if partner_exp_member is None:
            # Get random experiment member if swap_partner isn't set for some reason
            partner_exp_member = ExperimentMember.objects.exclude(user_id=cur_exp_member.user_id).order_by("?").first()
            cur_exp_member.swap_partner = partner_exp_member
            cur_exp_member.save()
        
        # Fetch new ad
        new_ad = None
        if orig_dim == "wide":
            # Filter for wide images at least as wide as this image
            ad_pks = models.AdRecord.objects.filter(participant_id=partner_exp_member).filter(intervenr_ad_type=models.IntervenrAdTypes.OBS).filter(img_width__gt=F("img_height")).filter(img_width__gte=orig_w).values_list('pk', flat=True)
            if len(ad_pks) > 0:
                sampled_pk = random.choice(ad_pks)
                new_ad = models.AdRecord.objects.get(pk=sampled_pk)
        else: 
            # Filter for tall images at least as tall as this image
            ad_pks = models.AdRecord.objects.filter(participant_id=partner_exp_member).filter(intervenr_ad_type=models.IntervenrAdTypes.OBS).filter(img_height__gte=F("img_width")).filter(img_height__gte=orig_h).values_list('pk', flat=True)
            if len(ad_pks) > 0:
                sampled_pk = random.choice(ad_pks)
                new_ad = models.AdRecord.objects.get(pk=sampled_pk)
        
        if new_ad is None:
            if debug:
                print("no matches")
            # No matches; find image that doesn't match size constraints
            ad_pks = models.AdRecord.objects.filter(participant_id=partner_exp_member).filter(intervenr_ad_type=models.IntervenrAdTypes.OBS).values_list('pk', flat=True)
            if len(ad_pks) > 0:
                sampled_pk = random.choice(ad_pks)
                new_ad = models.AdRecord.objects.get(pk=sampled_pk)
            else:
                # No valid swap ads; don't try to swap
                return JsonResponse({})
        else:
            if debug:
                print(f"{orig_dim} match: orig=({orig_w}, {orig_h}), new=({new_ad.img_width}, {new_ad.img_height})")
        new_ad_orig_id = new_ad.record_id

        results = {
            "img_src": new_ad.img_src,
            "target_url": new_ad.target_url,
        }

        # Save ad to the user's ad records
        new_ad.pk = None  # create new record
        new_ad.record_id = uuid.uuid4()  # create new record
        new_ad._state.adding = True
        new_ad.participant_id = cur_exp_member
        new_ad.created_time = datetime.datetime.now()
        new_ad.intervenr_ad_type = models.IntervenrAdTypes.INTERV_SWAP
        new_ad.original_ad = models.AdRecord.objects.filter(record_id=new_ad_orig_id)[0]

        # Save source page fields
        new_ad.src_page_title=orig_ad["pageTitle"]
        new_ad.src_page_url=orig_ad["pageUrl"]
        new_ad.page_domain=orig_ad["pageDomain"]

        new_ad.save()

        if debug:
            print(f"ads_extension action results (partner {partner_exp_member.contact_email})")
        return JsonResponse(results)

# Handles extension alerts
class UpdateView(ExtensionView):
    # TODO: add extension alerts in the future
    # Will use ExtensionAlert class
    def post(self, request):
        return

# Collects ads from extension side
class CollectAdsView(ExtensionView):
    def parse_ads_json(self, ad, request, limit=1, debug=False):
        # Print ad info
        if debug:
            print("src_page_hash", ad["pageHash"])
            print("ad_hash", ad["adHash"])
            print("content_type", ad["contentType"])
            print("ad_title", ad["title"])
            print("target_url", ad["targetUrl"])
            print("src_page_title", ad["pageTitle"])
            print("src_page_url", ad["pageUrl"])
            print("ad_network", "") # TODO: add

            content_type = ad["contentType"]
            if content_type == "img":
                print("img_src", ad["contentData"]["src"])
                print("img_width", ad["contentData"]["width"])
                print("img_height", ad["contentData"]["height"])
            elif content_type == "text":
                print("text_title", ad["contentData"]["title"])
                print("text_body_text", ad["contentData"]["text"])
                print("text_site", ad["contentData"]["site"])

        # Save info to DB
        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)
        content_type = ad["contentType"]
        
        # Set ad type based on experimental phase
        cur_ad_type = self.get_intervenr_ad_type()
            
        new_ad_record = models.AdRecord(
            participant_id=experiment_member,
            src_page_hash=ad["pageHash"],
            ad_hash=ad["adHash"],
            content_type=content_type,
            ad_title=ad["title"],
            target_url=ad["targetUrl"],
            src_page_title=ad["pageTitle"],
            src_page_url=ad["pageUrl"],
            ad_network=None,  # TODO: add ad network to json outputs
            page_domain=ad["pageDomain"],
            target_domain=ad["targetDomain"],
            target_hostname=ad["targetHostname"],
            # Image ad attributes
            img_src=(ad["contentData"]["src"] if (content_type == "img") else None),
            img_width=(ad["contentData"]["width"] if (content_type == "img") else None),
            img_height=(ad["contentData"]["height"] if (content_type == "img") else None),
            # Text ad attributes
            text_title=(ad["contentData"]["title"] if (content_type == "text") else None),
            text_body_text=(ad["contentData"]["text"] if (content_type == "text") else None),
            text_site=(ad["contentData"]["site"] if (content_type == "text") else None),
            intervenr_ad_type=cur_ad_type,
        )
        
        new_ad_record.save()


    def post(self, request, debug=False):
        if PAUSE_STUDY:
            return JsonResponse({})

        data = json.loads(request.body)
        if debug:
            print("val", data["val"])

        ads_json = data["ads_json"]
        if debug:
            print("ads_json", ads_json)

        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectAdsView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectAdsView': 'Error, invalid ExperimentMember record.', 'success': False})
        
        self.parse_ads_json(ads_json, request)

        results = {
            "res": "example_result_string",
        }
        return JsonResponse(results)

class CollectSeenAdsView(ExtensionView):
    def post(self, request):
        if PAUSE_STUDY:
            return JsonResponse({})

        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectSeenAdsView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectSeenAdsView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        last_matching_ads = models.AdRecord.objects.filter(img_src=data['fullUrl']).filter(participant_id=experiment_member)
        if last_matching_ads:
            last_matching_ad = last_matching_ads.latest('created_time')
            last_matching_ad.view_count = F('view_count') + 1
            last_matching_ad.save()

        # Now just return success
        return JsonResponse({'success': True})

class CollectClickedAdsView(ExtensionView):
    def post(self, request):
        if PAUSE_STUDY:
            return JsonResponse({})

        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectClickedAdsView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectClickedAdsView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        ad_img_src = data["img_src"]
        if ad_img_src is None:
            return JsonResponse({'CollectClickedAdsView': 'Error, non-image ad', 'success': False})

        last_matching_ads = models.AdRecord.objects.filter(img_src=ad_img_src).filter(participant_id=experiment_member)
        if last_matching_ads:
            last_matching_ad = last_matching_ads.latest('created_time')
            last_matching_ad.click_count = F('click_count') + 1
            last_matching_ad.save()

        # Now just return success
        return JsonResponse({'success': True})
