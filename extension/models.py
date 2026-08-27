from django.db import models
from frontend.models import ExperimentMember
import datetime
import uuid


# The URL Records from Link Trails
class UrlRecord(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    record_id = models.UUIDField(default=uuid.uuid4, editable=False)
    previous_record = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True)
    has_previous_record = models.BooleanField(blank=True, null=True)
    url = models.TextField(max_length=2000)
    tld = models.TextField(max_length=256)
    tld_record = models.ForeignKey('TldRecord', on_delete=models.SET_NULL, blank=True, null=True)
    current_tab_id = models.IntegerField()
    previous_tab_id = models.IntegerField(blank=True, null=True)
    transition_type = models.CharField(max_length=200)
    start_time = models.DateTimeField(default=datetime.datetime.now)
    end_time = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'{self.url}'

    class Meta:
        ordering = ['-start_time', '-end_time']
    

class URLMetadata(models.Model):
    participant_id = models.UUIDField()
    url_record_id = models.UUIDField()
    data_type = models.TextField()
    metadata = models.JSONField(blank=True, null=True)


class TweetSocialContext(models.IntegerChoices):
    NONE = 0  # No additional social context for the tweet
    RETWEETED = 1  # Tweet shows up on feed because it was retweeted by someone you follow
    LIKED = 2  # Tweet shows up on feed because it was liked by someone you follow


class TweetFeedType(models.IntegerChoices):
    OTHER = 0  # Tweet is not from the "For you" or "Following" tabs on the home page
    FOR_YOU = 1  # Tweet is from the "For you" tab on the home page
    FOLLOWING = 2  # Tweet is from the "Following" tab on the home page


# Tweet Record Model
class TweetRecord(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    record_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_time = models.DateTimeField(default=datetime.datetime.now)

    user_handle = models.CharField(blank=True, null=True, max_length=256)

    parent_page_url_record = models.ForeignKey(UrlRecord, on_delete=models.CASCADE, blank=True, null=True)
    tweet_src = models.TextField(blank=True, null=True)
    tweet_social_context = models.IntegerField(choices=TweetSocialContext.choices, default=0)
    tweet_feed_type = models.IntegerField(choices=TweetFeedType.choices, default=0)
    tweet_body_text = models.TextField(blank=True, null=True)
    tweet_visible_links = models.JSONField(blank=True, null=True)
    tweet_promoted = models.BooleanField(default=False)
    tweet_verified = models.BooleanField(default=False)

    # Tweet engagement attributes
    retweet_was_clicked = models.BooleanField(default=False)
    like_was_clicked = models.BooleanField(default=False)
    reply_was_clicked = models.BooleanField(default=False)

    duration = models.DurationField(default=datetime.timedelta(seconds=0))

    def __str__(self):
        return f'{self.tweet_src}'

    class Meta:
        ordering = ['-created_time']


class TweetMetadata(models.Model):
    participant_id = models.UUIDField()
    tweet_record_id = models.UUIDField()
    data_type = models.TextField()
    metadata = models.JSONField(blank=True, null=True)


# The Intervention Record Model
class DailyInterventionCount(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    date = models.DateTimeField(default=datetime.date.today, editable=False)
    tld_record = models.ForeignKey('TldRecord', on_delete=models.SET_NULL, blank=True, null=True)
    visit_count = models.IntegerField()
    intervention_type = models.TextField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.tld_record} on {self.date.strftime('%m/%d/%y')}: {self.visit_count}"

    class Meta:
        ordering = ['-date']


# The daily count of visible links for each participant
class DailyVisibleLinkCount(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    date = models.DateTimeField(default=datetime.date.today, editable=False)
    visible_link_count = models.IntegerField()
    
    def __str__(self):
        return f"{self.participant_id} on {self.date.strftime('%m/%d/%y')}: {self.visible_link_count}"
    
    class Meta:
        ordering = ['-date']   


# The Visible Links Record Model
class VisibleLinkRecord(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    parent_page_url_record = models.ForeignKey(UrlRecord, on_delete=models.CASCADE, blank=True, null=True)
    visible_timestamp = models.DateTimeField(default=datetime.datetime.now, editable=False)
    parent_tld = models.ForeignKey('TldRecord', on_delete=models.SET_NULL, blank=True, null=True,
                                   related_name='visible_link_parent_tlds')
    parent_page_url = models.CharField(max_length=2000)
    linked_tld = models.ForeignKey('TldRecord', on_delete=models.SET_NULL, blank=True, null=True, default=None,
                                   related_name='visible_link_link_tlds')
    linked_tld_url = models.CharField(max_length=2000, blank=True, null=True)
    linked_url = models.CharField(max_length=2000)
    referrer_url = models.CharField(max_length=2000, blank=True, null=True)
    tagname = models.TextField(max_length=6)
    is_intersecting = models.BooleanField()
    is_visible = models.BooleanField()
    visibility_available = models.BooleanField()
    duration = models.DurationField(default=datetime.timedelta(seconds=0))

    def __str__(self):
        return f'{self.linked_url}'

    class Meta:
        ordering = ['-visible_timestamp']


class VisibleLinkMetadata(models.Model):
    participant_id = models.UUIDField()
    visible_link_record_id = models.UUIDField()
    visible_link_id = models.IntegerField(blank=True, null=True)
    data_type = models.TextField()
    metadata = models.JSONField(blank=True, null=True)


# The Top Level Domains (TLD) Records
class TldRecord(models.Model):
    tld = models.TextField(max_length=256)
    apply_intervention = models.BooleanField()
    apply_collect_links = models.BooleanField()

    def __str__(self):
        return f'{self.tld}'


# Alert Message Objects Records
class ExtensionAlert(models.Model):
    # By default, set a date so we can get the latest alert for people
    alert_date = models.DateTimeField(default=datetime.datetime.now)
    # Who to alert: all, intervention class
    participant_alert_all = models.BooleanField(default=False)
    # Specific Intervention Class
    participant_alert_intervention_type = models.CharField(max_length=100)
    # Participant Message max of 17 chars in order to fit in extension popup
    participant_message = models.CharField(max_length=17)
    participant_alert_url = models.CharField(max_length=2000)
    participant_alert_active = models.BooleanField(default=False)

    def __str__(self):
        return f'Alert: {self.participant_message}, Link: {self.participant_alert_url}'


# Error Logs for Extension
class ExtensionError(models.Model):
    log_time = models.DateTimeField(default=datetime.datetime.now)
    request_json = models.JSONField()
    message = models.CharField(max_length=256, default="NA")

    def __str__(self):
        return f'Error at {self.log_time}: {self.message}'
