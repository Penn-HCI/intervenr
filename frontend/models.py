from django.db import models
from django.contrib.auth.models import User
import uuid
import datetime
import random


# Get random group for experiment
def rand_experimental_group():
    return random.choice(['for you', 'following'])

class ExperimentTypes(models.IntegerChoices):
    NOT_ASSIGNED = 0
    NEWS = 1
    ADS = 2

# Experiment member class itself
class ExperimentMember(models.Model):
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    social_auth = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    creation_date = models.DateTimeField(default=datetime.datetime.now, editable=False)
    extension_registered = models.BooleanField(default=False)
    offboard_user = models.BooleanField(default=False)
    offboard_date = models.DateTimeField(blank=True, null=True)
    contact_email = models.EmailField(blank=True)
    # Note, make everybody randomly choose between control, light, and heavy
    intervention_type = models.CharField(max_length=100, blank=True, default=rand_experimental_group, null=True)
    onboard_survey = models.BooleanField(default=False) # Corresponds to intro survey
    middle_survey = models.BooleanField(default=False) # Corresponds to midpoint survey
    second_middle_survey = models.BooleanField(default=False) # Corresponds to additional midpoint survey for 3 phase studies
    offboard_survey = models.BooleanField(default=False) # Corresponds to final survey
    first_q = models.TextField(max_length=2000, blank=True)
    second_q = models.TextField(max_length=2000, blank=True)
    experiment_type = models.IntegerField(choices=ExperimentTypes.choices, default=0)
    has_onboard_permission = models.BooleanField(default=False)
    has_onboarded = models.BooleanField(default=False)
    onboard_date = models.DateTimeField(blank=True, null=True)
    swap_partner = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, default=None) # Ad swap partner

    # now, add this function for the template
    def get_experiment_day(self):
        return (datetime.datetime.now() - self.creation_date).days

    def __str__(self):
        return f'User ID: {self.user_id}, {self.contact_email}'

class ExperimentSettings(models.Model):
    exp_name = models.TextField(default="", blank=True)
    creation_date = models.DateTimeField(default=datetime.datetime.now, editable=False)

    obs_start = models.DateField(default=datetime.date.today, editable=True)
    obs_end = models.DateField(default=None, editable=True)

    interv_start = models.DateField(default=None, editable=True)
    interv_end = models.DateField(default=None, editable=True)

class IntroSurvey(models.Model):
    user_id = models.OneToOneField(ExperimentMember, on_delete=models.CASCADE)
    created_time = models.DateTimeField(default=datetime.datetime.now)
    response_json = models.JSONField(null=True)

    def __str__(self):
        return f'IntroSurvey: {self.user_id}'

class MidpointSurvey(models.Model):
    user_id = models.OneToOneField(ExperimentMember, on_delete=models.CASCADE)
    created_time = models.DateTimeField(default=datetime.datetime.now)
    response_json = models.JSONField(null=True)

    def __str__(self):
        return f'MidpointSurvey: {self.user_id}'
    
class FinalSurvey(models.Model):
    user_id = models.OneToOneField(ExperimentMember, on_delete=models.CASCADE)
    created_time = models.DateTimeField(default=datetime.datetime.now)
    response_json = models.JSONField(null=True)

    def __str__(self):
        return f'FinalSurvey: {self.user_id}'
    
class SecondMidpointSurvey(models.Model):
    user_id = models.OneToOneField(ExperimentMember, on_delete=models.CASCADE)
    created_time = models.DateTimeField(default=datetime.datetime.now)
    response_json = models.JSONField(null=True)

    def __str__(self):
        return f'SecondMidpointSurvey: {self.user_id}'
