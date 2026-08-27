from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import django.db.models as djModels

from extension.models import TweetSocialContext, TweetFeedType
from frontend.models import ExperimentMember, MidpointSurvey, SecondMidpointSurvey, ExperimentTypes
from extension import models
from urllib.parse import urlparse
import datetime
import json
import uuid
import logging

PAUSE_STUDY = True

# Logger to assist in live debugging
logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ExtensionView(View):
    def is_valid_experiment_member(self, request):
        data = json.loads(request.body)
        uuid_value = data['ParticipantId']
        uuid_obj = uuid.UUID(uuid_value)
        return bool(ExperimentMember.objects.filter(user_id=uuid_obj, experiment_type=ExperimentTypes.NEWS).exists())

    def get_experiment_member(self, data):
        uuid_value = data['ParticipantId']
        uuid_obj = uuid.UUID(uuid_value)
        return ExperimentMember.objects.get(user_id=uuid_obj, experiment_type=ExperimentTypes.NEWS)

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

    def get_url_tld(self, data):
        parsed_url = urlparse(data['url'])
        parsed_tld = parsed_url.hostname
        if not parsed_tld:
            return "tld"
        return parsed_tld

    def get_tld_record_or_none(self, data):
        parsed_url = urlparse(data['url'])
        parsed_tld = parsed_url.hostname if parsed_url.hostname else ""
        if "":
            print(data['url'])
        if models.TldRecord.objects.filter(tld=parsed_tld).exists():
            tld_record = models.TldRecord.objects.filter(tld=parsed_tld).first()
            return tld_record
        if parsed_tld.startswith('www.') and models.TldRecord.objects.filter(tld=parsed_tld[4:]).exists():
            tld_record = models.TldRecord.objects.filter(tld=parsed_tld[4:]).first()
            return tld_record
        else:
            return None

    def get_prev_tab_or_none(self, data):
        if data['prevTabId']:
            return data['prevTabId']
        else:
            return None


class StartUrlView(ExtensionView):
    # Get the previous url record or just return none
    def get_prev_url_record_or_none(self, data):
        if data['prevTabId'] and type(data['previousRecord']) != bool:
            prev_url_record_uuid = uuid.UUID(data['previousRecord'])
            prev_url_record = models.UrlRecord.objects.filter(record_id=prev_url_record_uuid)
            if prev_url_record.exists():
                return prev_url_record[0]
            else:
                self.log(data=data, message="StartUrlView: previousRecord defined but not found in UrlRecord objects.")
        return None

    def post(self, *args, **kwargs):
        if PAUSE_STUDY:
            return JsonResponse({})
        request = args[0]
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="StartUrlView: invalid ExperimentMember object code.")
            return JsonResponse({'StartUrlView': 'Error, data invalid.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)
        prev_url_record = self.get_prev_url_record_or_none(data)
        new_url_record = models.UrlRecord(
            participant_id=experiment_member,
            previous_record=prev_url_record,
            has_previous_record=bool(prev_url_record),
            url=data['url'],
            tld=self.get_url_tld(data),
            tld_record=None,
            current_tab_id=data['currTabId'],
            previous_tab_id=self.get_prev_tab_or_none(data),
            transition_type=data['transition'],
        )
        new_url_record.save()
        return JsonResponse({'recordId': str(new_url_record.record_id), 'success': True})


class EndUrlView(ExtensionView):
    # Get the last record or return none
    def get_url_record_or_none(self, data):
        if data['recordId']:
            initial_url_uuid = uuid.UUID(data['recordId'])
            start_url_record = models.UrlRecord.objects.filter(record_id=initial_url_uuid)
            if start_url_record.exists():
                return start_url_record[0]
            else:
                self.log(data=data, message="EndUrlView: matching recordId not found in UrlRecord objects.")
        return None

    def post(self, *args, **kwargs):
        if PAUSE_STUDY:
            return JsonResponse({})
        request = args[0]
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="EndUrlView: invalid ExperimentMember object code.")
            return JsonResponse({'EndUrlView': 'Error, ParticipantId invalid.', 'success': False})

        data = json.loads(request.body)
        url_record = self.get_url_record_or_none(data)
        if url_record:
            url_record.end_time = datetime.datetime.now()
            url_record.save()
            return JsonResponse({'EndUrlView': 'URL Record successfully updated.', 'success': True,
                                 'recordId': str(url_record.record_id)})
        return JsonResponse(
            {'EndUrlView': 'Error, URL recordId invalid', 'success': False, 'recordId': data['recordId']})


class UpdateView(ExtensionView):
    # check for general updates and individual level updates, and also hosts the offboard switch
    def post(self, request):
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="UpdateView: invalid ExperimentMember object code.")
            return JsonResponse({'UpdateView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)
        response_dict = {
            'ParticipantAlert': False,
            'ParticipantAlertMessage': "",
            'ParticipantAlertUrl': "",
            'COLLECT_LINKS_TRUE_VISIBILITY': True,
            'success': True,
        }

        if experiment_member.offboard_user:
            response_dict['OFFBOARD_USER'] = True

        if models.ExtensionAlert.objects.exists():
            latest_alert = models.ExtensionAlert.objects.latest('alert_date')
            if experiment_member.intervention_type == latest_alert.participant_alert_intervention_type or latest_alert.participant_alert_all:
                response_dict['ParticipantAlert'] = latest_alert.participant_alert_active
                response_dict['ParticipantAlertMessage'] = latest_alert.participant_message
                response_dict['ParticipantAlertUrl'] = latest_alert.participant_alert_url

        return JsonResponse(response_dict)


class ActionView(ExtensionView):
    # DAY_THRESHOLD sets the threshold at which the intervention will start being applied
    DAY_THRESHOLD = 7

    def updateDailyInterventionCount(self, experiment_member, matched_tld_record):
        matching_intervention_count = models.DailyInterventionCount.objects.filter(
            tld_record=matched_tld_record,
            participant_id=experiment_member,
            intervention_type=experiment_member.intervention_type,
            date__date=datetime.date.today()
        )
        if matching_intervention_count.exists():
            curr_count = matching_intervention_count.first()
            curr_count.visit_count += 1
            curr_count.save()
        else:
            curr_count = models.DailyInterventionCount(
                participant_id=experiment_member,
                tld_record=matched_tld_record,
                visit_count=1,
                intervention_type=experiment_member.intervention_type,
            )
            curr_count.save()

    """
    apply_intervention_logic
    This function actually defines the logic of interventions that will be returned to the extension client
    NOTE: this must provide the following parameters to the response dict
        intervention - str of type light, heavy, control depending on what should execute for the user
        apply_intervention - bool for whether the intervention script should be directly injected into the website
        intervention_message - str that has html for the message to display to the user
    """
    def apply_intervention_logic(self, response_dict, matched_tld_record, experiment_member):
        user_threshold_time = experiment_member.onboard_date.date() + datetime.timedelta(days=ActionView.DAY_THRESHOLD)
        midpointSurveyCompleted = True if MidpointSurvey.objects.filter(user_id=experiment_member) else False
        if user_threshold_time < datetime.date.today() and midpointSurveyCompleted:
            # DAY_THRESHOLD days have passed since the user onboarded. Apply intervention.
            # Before we apply intervention, update the DailyInterventionCount
            self.updateDailyInterventionCount(experiment_member, matched_tld_record)
            response_dict['apply_intervention'] = True
            response_dict['intervention_message'] = 'Applying Twitter Intervention'
        return response_dict

    # Get interventions for a URL, and update URL tld visit counts
    def post(self, request):
        if PAUSE_STUDY:
            return JsonResponse({})
        
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="ActionView: invalid ExperimentMember object code.")
            return JsonResponse({'ActionView': 'Error, invalid ExperimentMember record.', 'success': False})

        # Setup data and response, by default no collect links and no interventions (control)
        response_dict = {'collect_links': False, 'collect_tweets': False, 'intervention': 'control',
                         'apply_intervention_now': False, 'success': True}
        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        # Check if they should be offboarded after this
        if experiment_member.offboard_user:
            response_dict['OFFBOARD_USER'] = True

        # Lookup the TLD Record to see if it's something we even have actions registered for
        # If not, just return a response that has both actions as false
        matched_tld_record = self.get_tld_record_or_none(data)
        if matched_tld_record and matched_tld_record.tld == "twitter.com":
            # Check if Twitter intervention should be applied.
            response_dict['intervention'] = experiment_member.intervention_type
            response_dict = self.apply_intervention_logic(response_dict, matched_tld_record, experiment_member)
            # Collect tweets.
            response_dict['collect_tweets'] = True
            response_dict['collect_links'] = True
        else:
            # Collect links on all sites
            response_dict['collect_links'] = True

        return JsonResponse(response_dict)


class CollectLinksView(ExtensionView):

    def updateDailyVisibleLinkCount(self, experiment_member):
        matching_daily_visible_link_count = models.DailyVisibleLinkCount.objects.filter(
            participant_id=experiment_member,
            date__date=datetime.date.today()
        )
        if matching_daily_visible_link_count.exists():
            curr_count = matching_daily_visible_link_count.first()
            curr_count.visible_link_count += 1
            curr_count.save()
        else:
            curr_count = models.DailyVisibleLinkCount(
                participant_id=experiment_member,
                visible_link_count=1,
            )
            curr_count.save()

    # This view will simply collect all link information passed in, and return a success or error on completion.
    def post(self, request):
        if PAUSE_STUDY:
            return JsonResponse({})
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectLinksView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectLinksView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        parent_url_record = models.UrlRecord.objects.filter(record_id=data['recordId']).first()
        visible_link_record = models.VisibleLinkRecord(
            participant_id=experiment_member,
            parent_page_url_record=parent_url_record,
            parent_tld=None,
            parent_page_url=data['currentWebPage'][:2000],
            linked_tld=None,
            linked_tld_url=None,
            linked_url=data['fullUrl'][:2000],
            referrer_url=data['referrerWebPage'][:2000],
            tagname=data['tagName'],
            is_intersecting=data['isIntersecting'],
            is_visible=data['isVisible'],
            visibility_available=data['trackVisibilityAvailable']
        )
        visible_link_record.save()

        self.updateDailyVisibleLinkCount(experiment_member)

        # Now just return success
        return JsonResponse({'success': True})

class CollectVisibleLinkDurationView(ExtensionView):
    def post(self, request, debug=False):
        return JsonResponse({'success': True})
        if PAUSE_STUDY:
            return JsonResponse({})
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectVisibleLinkDurationView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectVisibleLinkDurationView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        linked_url = data["fullUrl"]
        if linked_url is None:
            return JsonResponse({'CollectVisibleLinkDurationView': 'Error, no link src url', 'success': False})
        duration = data["intersectDuration"]
        if duration is None:
            return JsonResponse({'CollectVisibleLinkDurationView': 'Error, no link visible duration', 'success': False})

        if debug:
            print("tweet_src", data["fullUrl"])
            print("duration", int(data["intersectDuration"]))
        
        last_matching_visible_links = models.VisibleLinkRecord.objects.filter(participant_id=experiment_member).filter(linked_url=linked_url)
        if last_matching_visible_links:
            last_matching_link = last_matching_visible_links.latest('visible_timestamp')
            last_matching_link.duration = last_matching_link.duration + datetime.timedelta(milliseconds=int(duration))
            last_matching_link.save()

        return JsonResponse({'success': True})



class CollectTweetsView(ExtensionView):
    def parse_tweets_json(self, tweet, request, debug=False):
        # Print tweet info
        if debug:
            print("tweet_src", tweet["tweetSrc"])
            print("tweet_social_context", tweet["tweetSocialContext"])
            print("tweet_body_text", tweet["tweetBodyText"])
            print("from_for_you_tab", TweetFeedType.FOR_YOU if tweet["fromForYouTab"] == True else TweetFeedType.FOLLOWING if tweet["fromForYouTab"] == False else TweetFeedType.OTHER)
            print("tweet_visible_links", tweet["tweetVisibleLinks"])
            print("tweet_promoted", tweet["tweetPromoted"])
            print("tweet_verified", tweet["tweetVerified"])
            print("record_id", tweet["recordId"])
            print("user_handle", tweet["userHandle"])

        # Save info to DB
        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        parent_url_record = models.UrlRecord.objects.filter(record_id=data['recordId']).first()

        new_tweet_record = models.TweetRecord(
            participant_id=experiment_member,
            user_handle=tweet["userHandle"],
            parent_page_url_record=parent_url_record,
            tweet_src=tweet["tweetSrc"],
            tweet_social_context=TweetSocialContext.RETWEETED if tweet["tweetSocialContext"] == "reposted" else TweetSocialContext.LIKED if tweet["tweetSocialContext"] == "Liked" else TweetSocialContext.NONE,
            tweet_feed_type=TweetFeedType.FOR_YOU if tweet["fromForYouTab"] == True else TweetFeedType.FOLLOWING if tweet["fromForYouTab"] == False else TweetFeedType.OTHER,
            tweet_body_text=tweet["tweetBodyText"],
            tweet_visible_links=tweet["tweetVisibleLinks"],
            tweet_promoted=tweet["tweetPromoted"],
            tweet_verified=tweet["tweetVerified"],
        )
        new_tweet_record.save()

    def post(self, request):
        if PAUSE_STUDY:
            return JsonResponse({})
        
        data = json.loads(request.body)

        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectTweetsView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectTweetsView': 'Error, invalid ExperimentMember record.', 'success': False})

        try:
            self.parse_tweets_json(data, request)
        except:
            logger.exception("CollectTweetsView: Exception in parse_tweets_json")

        return JsonResponse({'success': True})


class CollectTweetEngagementsView(ExtensionView):
    def post(self, request, debug=False):
        if PAUSE_STUDY:
            return JsonResponse({})
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectTweetsView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectTweetsView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        tweet_src = data["tweetSrc"]
        if tweet_src is None:
            return JsonResponse({'CollectRetweetedTweetsView': 'Error, no tweet src url', 'success': False})

        if debug:
            print("tweet_src", data["tweetSrc"])
            print("engagement_type", data["engagementType"])

        last_matching_tweets = models.TweetRecord.objects.filter(tweet_src=tweet_src).filter(
            participant_id=experiment_member)
        if last_matching_tweets:
            last_matching_tweet = last_matching_tweets.latest('created_time')
            if data["engagementType"] == "reply":
                last_matching_tweet.reply_was_clicked = True
            elif data["engagementType"] == "retweet":
                last_matching_tweet.retweet_was_clicked = True
            elif data["engagementType"] == "like":
                last_matching_tweet.like_was_clicked = True
            else:
                self.log(request=request, message="CollectTweetEngagementsView: invalid tweet engagement type.")
                return JsonResponse(
                    {'CollectTweetEngagementsView': 'Error, invalid tweet engagement type.', 'success': False})
            last_matching_tweet.save()
        return JsonResponse({'success': True})


class CollectTweetVisibleDurationView(ExtensionView):
    def post(self, request, debug=False):
        if PAUSE_STUDY:
            return JsonResponse({})
        if not self.is_valid_experiment_member(request):
            self.log(request=request, message="CollectTweetVisibleDurationView: invalid ExperimentMember object code.")
            return JsonResponse({'CollectTweetVisibleDurationView': 'Error, invalid ExperimentMember record.', 'success': False})

        data = json.loads(request.body)
        experiment_member = self.get_experiment_member(data)

        tweet_src = data["tweetSrc"]
        if tweet_src is None:
            return JsonResponse({'CollectTweetVisibleDurationView': 'Error, no tweet src url', 'success': False})
        duration = data["intersectDuration"]
        if duration is None:
            return JsonResponse({'CollectTweetVisibleDurationView': 'Error, no tweet visible duration', 'success': False})

        if debug:
            print("tweet_src", data["tweetSrc"])
            print("duration", int(data["intersectDuration"]))
        last_matching_tweets = models.TweetRecord.objects.filter(tweet_src=tweet_src).filter(
            participant_id=experiment_member)
        if last_matching_tweets:
            last_matching_tweet = last_matching_tweets.latest('created_time')
            last_matching_tweet.duration = last_matching_tweet.duration + datetime.timedelta(milliseconds=int(duration))
            last_matching_tweet.save()
        return JsonResponse({'success': True})
