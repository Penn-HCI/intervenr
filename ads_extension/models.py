from django.db import models
from django.utils.html import mark_safe
import datetime
import uuid

from frontend.models import ExperimentMember

class IntervenrAdTypes(models.IntegerChoices):
    OBS = 0  # An ad delivered to user during observational phase
    INTERV_ORIG = 1  # An ad *originally* delivered to the user during the intervention phase (which was swapped out)
    INTERV_SWAP = 2  # The ad that was *actually* delivered to the user during the intervention phase (which was swapped in)
    TO_IGNORE = 3  # Ads outside of the observational and intervention phases

# Keeps track of collected ads data
class AdRecord(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    record_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_time = models.DateTimeField(default=datetime.datetime.now)

    # ADN attributes
    src_page_hash = models.TextField()
    ad_hash = models.TextField()
    content_type = models.TextField()
    ad_title = models.TextField()
    target_url = models.TextField()
    src_page_title = models.TextField()
    src_page_url = models.TextField()
    ad_network = models.TextField(blank=True, null=True)
    page_domain = models.TextField(blank=True, null=True)
    target_domain = models.TextField(blank=True, null=True)
    target_hostname = models.TextField(blank=True, null=True)

    # Image ad attributes
    img_src = models.TextField(blank=True, null=True)
    img_width = models.IntegerField(blank=True, null=True)
    img_height = models.IntegerField(blank=True, null=True)

    # Text ad attributes
    text_title = models.TextField(blank=True, null=True)
    text_body_text = models.TextField(blank=True, null=True)
    text_site = models.TextField(blank=True, null=True)

    # User behavior attributes
    view_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)

    # Intervention attributes
    intervenr_ad_type = models.IntegerField(choices=IntervenrAdTypes.choices, default=0)
    original_ad = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True)  # link to original AdRecord if ad is a swapped ad

    # Post-processing
    img_was_downloaded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ad_hash}: {self.content_type} ad, target url {self.target_url}"

    @property
    def img_preview(self):
        if self.img_src:
            return mark_safe(f'<img src="{self.img_src}", width="{self.img_width}", height="{self.img_height}">')
    
    class Meta:
        ordering = ['-created_time']

class AdRecordRedaction(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    record_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_time = models.DateTimeField(default=datetime.datetime.now)
    n_deleted = models.IntegerField(default=0)

class ClientIP(models.Model):
    participant_id = models.ForeignKey(ExperimentMember, on_delete=models.CASCADE, editable=False)
    ip = models.TextField(blank=True, null=True)
    created_time = models.DateTimeField(default=datetime.datetime.now)

# Each row stores a particular element of extracted metadata from an AdRecord that's been collected from a participant
class AdMetadata(models.Model):
    participant_id = models.UUIDField()
    ad_record_id = models.UUIDField()
    extraction_method = models.TextField()  # Indicates the method used to extract the metadata (ex: pytesseract, Deepface)
    data_type = models.TextField()  # Indicates what kind of metadata is stored in this row (ex: OCR, gender, race, image objects)
    metadata = models.JSONField(blank=True, null=True)

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
