from django import forms
from django.utils.safestring import mark_safe
from ads_extension import models as ads_extension_models
import random
from django.conf import settings
import os
import pickle
from intervenr.settings.base import RUNNING_PROD

from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Fieldset, HTML

class UrlRedactionForm(forms.Form):
    redaction_list = forms.JSONField(required=False)

class AdRedactionForm(forms.Form):
    redaction_list = forms.JSONField(required=False)

class ContactEmailForm(forms.Form):
    contact_email = forms.EmailField(label="Please enter your new contact email:")


class SAJsonDataForm(forms.Form):
    json_data = forms.JSONField(required=False)

def bold_label(l1, l2=None):
    if l2 is None:
        return mark_safe("<b>" + l1 + "</b>")
    else:
        return mark_safe("<b>" + l1 + "</b> " + l2)

def get_likert_choices(lo, hi):
    return [("1", f"Very {lo}"), ("2", f"{lo}".capitalize()), ("3", f"Somewhat {lo}"), ("4", f"Neither"), ("5", f"Somewhat {hi}"), ("6", f"{hi}".capitalize()), ("7", f"Very {hi}"),]

def get_5_point_likert_choices(lo, hi):
    return [("1", f"Extremely {lo}"), ("2", f"Somewhat {lo}"), ("3", f"Neither {lo} nor {hi}"), ("4", f"Somewhat {hi}"), ("5", f"Extremely {hi}")]

def add_no_image_option(opts):
    new_opts = opts.copy()
    new_opts.append(("no_image", "N/A (select if image is not appearing)"))
    return new_opts

YES_NO_CHOICES = [("No", "No"), ("Yes", "Yes")]
YES_NO_UNSURE_CHOICES = [("No", "No"), ("Yes", "Yes"), ("Unsure", "Unsure")]

FREQ_CHOICES = [("1", "Never (0% of the time)"), ("2", "Rarely (<10% of the time)"), ("3", "Occasionally (<30% of the time)"), ("4", "Sometimes (~50% of the time)"), ("5", "Frequently (<70% of the time)"), ("6", "Usually (<90% of the time)"), ("7", "Always (100% of the time)"),]

PCT_CHOICES = [("1", "None (0%)"), ("2", " Few (<10%)"), ("3", "Some (<30%)"), ("4", "About half (~50%)"), ("5", "Many (<70%)"), ("6", "Most (<90%)"), ("7", "All (100%)"),]

AGREEMENT_CHOICES = [
    ('1', 'Strongly disagree'),
    ('2', 'Somewhat disagree'),
    ('3', 'Neither agree nor disagree'),
    ('4', 'Somewhat agree'),
    ('5', 'Strongly agree')
]

if RUNNING_PROD:
    # AWS setup
    BUCKET = 'inadvertent-images'
    session = boto3.Session(
        aws_access_key_id=os.environ['AWS_S3_IMGS_ACCESS_KEY'],
        aws_secret_access_key=os.environ['AWS_S3_IMGS_SECRET_KEY'],
    )

    # Generate a presigned URL for the S3 object
    s3_client = session.client('s3')

    cached_ad_urls = []
    cached_final_ad_urls = []

    # with open(os.path.join(settings.STATIC_ROOT, 'data/22_07_25_ad_urls.pkl'), "rb") as f:
    #     cached_ad_urls = pickle.load(f)
    
    # with open(os.path.join(settings.STATIC_ROOT, 'data/22_08_02_ad_urls_finalSurv.pkl'), "rb") as f:
    #     cached_final_ad_urls = pickle.load(f)

# Generate pre-signed URL to S3 objects
def create_presigned_url(ad, expiration=604800):
        """Generate a presigned URL to share an s3 object
        Arguments:
            ad_id {str} -- Required. AdRecord object.
        Keyword Arguments:
            expiration {int} -- Expiration in seconds (default: {604800 = 7 days})
        Returns:
            Optional[str] -- Presigned url of s3 object. If error, returns None.
        """
        if not RUNNING_PROD:
            return ad.img_src

        ad_id = ad.record_id
        if str(ad_id) in cached_final_ad_urls:
            cur_url = cached_final_ad_urls[str(ad_id)]
            if cur_url == "":
                # Try to fetch img_src string
                cur_url = ad.img_src
                if cur_url is None:
                    # If it's null, return placeholder string
                    return "None"
                return ad.img_src
            return cur_url
        elif str(ad_id) in cached_ad_urls:
            return cached_ad_urls[str(ad_id)]

        created_time = ad.created_time + timedelta(days=1)
        date = created_time.strftime("%Y-%m-%d")
        object_name = f"ad_images/{date}/{ad_id}.png"

        try:
            response = s3_client.generate_presigned_url('get_object',
                                                        Params={
                                                            'Bucket': BUCKET,
                                                            'Key': object_name
                                                        },
                                                        ExpiresIn=expiration)
        except ClientError as e:
            return ad.img_src

        # The response contains the presigned URL
        return response


class IntroSurveyForm(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)

    ad_blocker_usage = forms.CharField(
        label=bold_label("Do you use an ad blocker ordinarily?", l2="Note: as a reminder, please disable any ad blockers during this study."), 
        widget=forms.RadioSelect(choices=YES_NO_CHOICES), 
        required=True
    )
    ad_blocker_reason = forms.CharField(
        label=bold_label("Why do you or don't you use an ad blocker?"), 
        widget=forms.Textarea(attrs={"rows": 5, "cols": 100}), 
        required=True
    )

    AD_PERC_FREQ_CHOICES = [("1", "Never (0% of the time)"), ("2", "Rarely (<10% of the time)"), ("3", "Occasionally (<30% of the time)"), ("4", "Sometimes (~50% of the time)"), ("5", "Frequently (<70% of the time)"), ("6", "Usually (<90% of the time)"), ("7", "Always (100% of the time)"),]
    ad_click_freq = forms.CharField(
        label=bold_label('How often do you <i>click</i> on online ads?'), 
        widget=forms.RadioSelect(choices=AD_PERC_FREQ_CHOICES), 
        required=True
    )

    AD_TIME_FREQ_CHOICES = [("1", "Never or less than once a year"), ("2", "About once a year"), ("3", "More than once a year"), ("4", "About once a month"), ("5", "More than once a month"), ("6", " About once a week"), ("7", "More than once a week"),]
    ad_search_freq = forms.CharField(
        label=bold_label('How often do you <i>separately search</i> for a product or opportunity that you’ve seen in an ad (rather than directly interacting with the ad)?', l2="Please choose the option that most precisely captures this frequency."), 
        widget=forms.RadioSelect(choices=AD_TIME_FREQ_CHOICES), 
        required=True
    )
    ad_purchase_freq = forms.CharField(
        label=bold_label('How often do you <i>purchase products</i> that you heard about through an ad?', l2="Please choose the option that most precisely captures this frequency."), 
        widget=forms.RadioSelect(choices=AD_TIME_FREQ_CHOICES), 
        required=True
    )

    AD_SENTIMENT_CHOICES = [("1", "Strongly dislike"), ("2", "Dislike"), ("3", "Slightly dislike"), ("4", "Neither"), ("5", "Slightly like"), ("6", "Like"), ("7", "Strongly like"),]
    ad_sentiment = forms.CharField(
        label=bold_label("Generally, how do you feel about online ads?"), 
        widget=forms.RadioSelect(choices=AD_SENTIMENT_CHOICES), 
        required=True
    )

    ad_useful = forms.CharField(
        label=bold_label("To what extent do you think ads are <i>useful</i>?"), 
        widget=forms.RadioSelect(choices=get_likert_choices("unuseful", "useful")), 
        required=True
    )

    ad_control = forms.CharField(
        label=bold_label("To what extent do you think you have <i>sufficient control</i> over the ads you see?"), 
        widget=forms.RadioSelect(choices=get_likert_choices("insufficient control", "sufficient control")), 
        required=True
    )

    AD_REVENUE_CHOICES = [("1", "Strongly disapprove"), ("2", "Disapprove"), ("3", "Slightly disapprove"), ("4", "Neither"), ("5", "Slightly approve"), ("6", "Approve"), ("7", "Strongly approve"),]
    ad_revenue_model = forms.CharField(
        label=bold_label("To what extent do you approve of ads as a revenue model for online services?"), 
        widget=forms.RadioSelect(choices=AD_REVENUE_CHOICES),
        required=True
    )


###### STUDY EXPERIENCE FORM
class SurveyExperienceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)

    study_experience = forms.CharField(
        label=bold_label("How has your experience in the study been?"), 
        widget=forms.RadioSelect(choices=get_likert_choices("negative", "positive")),
        required=True
    )
    study_rec = forms.CharField(
        label=bold_label("How likely are you to recommend a friend to participate in this study?"), 
        widget=forms.RadioSelect(choices=get_likert_choices("unlikely", "likely")),
        required=True
    )
    compliance_extension = forms.CharField(
        label=bold_label("How often have you disabled the extension to avoid our ad tracking?"), 
        widget=forms.RadioSelect(choices=FREQ_CHOICES),
        required=True
    )
    compliance_incognito = forms.CharField(
        label=bold_label("How often have you used incognito mode to avoid our ad tracking?"), 
        widget=forms.RadioSelect(choices=FREQ_CHOICES),
        required=True
    )
    other_comments = forms.CharField(
        label=bold_label("(Optional) Please feel free to share any other comments you may have about the study."), 
        widget=forms.Textarea(attrs={"rows": 5, "cols": 100}), 
        required=False
    )

class MidpointSurveyExperienceForm(SurveyExperienceForm):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)

class FinalSurveyExperienceForm(SurveyExperienceForm):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)
        self.order_fields(["study_experience", "study_rec", "compliance_extension", "compliance_incognito", "freetext_interest", "freetext_rep", "freetext_missing", "other_comments"])
    
    freetext_interest = forms.CharField(
        label=bold_label("During this pilot study, we’ve asked you about your <i>interest</i> in some of the ads you’ve seen. Do you have any reflections about your overall experience with online ads, especially with regard to your interest in them?<br>"), 
        widget=forms.Textarea(attrs={"rows": 5, "cols": 100}), 
        required=True
    )
    freetext_rep = forms.CharField(
        label=bold_label("We’ve also asked you about how <i>represented</i> you feel by some ads or whether they <i>resonate</i> with you. Do you have any reflections about your overall experience with online ads regarding your feeling of representation?<br>"), 
        widget=forms.Textarea(attrs={"rows": 5, "cols": 100}), 
        required=True
    )
    freetext_missing = forms.CharField(
        label=bold_label("Is there anything related to your experience of online advertising that <i>hasn’t</i> been adequately captured by our survey questions? (For example, aspects of online ads that are problematic for you or, conversely, that are especially valuable to you?)<br>"), 
        widget=forms.Textarea(attrs={"rows": 5, "cols": 100}), 
        required=True
    )


###### ADS SAMPLE FORM (PER-AD QUESTIONS)
class SurveyAdsSampleForm(forms.Form):
    def get_ad_id_field(self, ad_record_id):
        return forms.CharField(
            label = "",
            widget = forms.TextInput(attrs = {'class': 'hidden'}),
            initial=ad_record_id,
            required=True,
        )
    def get_ad_url_field(self, ad_url):
        return forms.CharField(
            label = "",
            widget = forms.TextInput(attrs = {'class': 'hidden'}),
            initial=ad_url,
            required=True,
        )
    def get_recall_field(self, i, ad_img_src):
        recall_question = f"Ad {i + 1}: Do you recall seeing this ad? (Note: we'll show some ads that were not delivered to you) <div><img src={ad_img_src} class='survey_ad_img'></div>"
        return forms.CharField(
            label=bold_label(recall_question),
            widget=forms.RadioSelect(choices=add_no_image_option(YES_NO_UNSURE_CHOICES)),
            required=True
        )
    def get_rep_field(self, i):
        rep_question = f"Ad {i + 1}: To what extent do you feel like this ad represents or resonates with you?"
        return forms.CharField(
            label=bold_label(rep_question),
            widget=forms.RadioSelect(choices=add_no_image_option(get_likert_choices("unrepresented", "represented"))),
            required=True
        )
    def get_interest_field(self, i):
        interest_question = f"Ad {i + 1}: How interested are you in this product/opportunity?"
        return forms.CharField(
            label=bold_label(interest_question),
            widget=forms.RadioSelect(choices=add_no_image_option(get_likert_choices("uninterested", "interested"))),
            required=True
        )
    
    def get_attn_check_hidden_field(self):
        return forms.CharField(
            label="",
            widget=forms.TextInput(attrs = {'class': 'hidden'}),
            initial="",
            required=False,
        ) 
    
    def get_attn_check_field(self, i):
        attn_check_img = "https://inadvertent-to-label.s3.us-west-2.amazonaws.com/1462660.jpg"
        attn_check_question = f"Ad {i + 1}: The following question is an attention check. You must select 'Somewhat interested' below to demonstrate that you are paying attention to this survey. <div><img src={attn_check_img} class='survey_ad_img'></div>"
        return forms.CharField(
            label=bold_label(attn_check_question),
            widget=forms.RadioSelect(choices=add_no_image_option(get_likert_choices("uninterested", "interested"))),
            required=True
        )
    
    def generate_category_fields(self, prefix, cur_ads, inds, ordered_fields, starting_i, add_attn_check):
        if add_attn_check:
            n_additional_fields = 4 
            cur_ind = inds[starting_i]
            # Add attention check once for this ad category
            self.fields[f"attn_check"] = self.get_attn_check_field(cur_ind)
            ordered_fields[cur_ind] = ["attn_check"]
            for i in range(n_additional_fields):
                cur_field_name = f"attn_check_hidden_{i}"
                self.fields[cur_field_name] = self.get_attn_check_hidden_field()
                ordered_fields[cur_ind].append(cur_field_name)
            
        else:
            # Normal survey question section
            n_cur_ads = len(cur_ads)
            for i in range(n_cur_ads):
                cur_ad = cur_ads[i]
                cur_ind = inds[starting_i + i]
                ad_presigned_url = create_presigned_url(cur_ad)
                self.fields[f"{prefix}_ad_{i}_record_id"] = self.get_ad_id_field(cur_ad.record_id) # Hidden Ad ID field
                self.fields[f"{prefix}_ad_{i}_url"] = self.get_ad_url_field(ad_presigned_url) # Hidden Ad URL field
                self.fields[f"{prefix}_ad_{i}_recall"] = self.get_recall_field(cur_ind, ad_presigned_url)
                self.fields[f"{prefix}_ad_{i}_rep"] = self.get_rep_field(cur_ind)
                self.fields[f"{prefix}_ad_{i}_interest"] = self.get_interest_field(cur_ind)
                ordered_fields[cur_ind] = [f"{prefix}_ad_{i}_record_id", f"{prefix}_ad_{i}_url", f"{prefix}_ad_{i}_recall", f"{prefix}_ad_{i}_rep", f"{prefix}_ad_{i}_interest"]

    def __init__(self, ad_sets=None, n_max=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)

        ALL_PREFIXES = [
            "user_seen_people", 
            "user_seen_noPeople", 
            "user_unseen_people", 
            "user_unseen_noPeople", 
            "other_people",
            "other_noPeople",
            "attn_check",
        ]

        # Generate new form
        if "initial" not in kwargs.keys():
            n_total = sum([len(ad_set) for ad_set in ad_sets.values() if ad_set is not None])
            inds = list(range(n_total))
            random.shuffle(inds)
            ordered_fields = {}

            starting_i = 0
            for cur_prefix, cur_ad_set in ad_sets.items():
                if cur_ad_set is not None:
                    add_attn_check = True if cur_prefix == "attn_check" else False
                    self.generate_category_fields(cur_prefix, cur_ad_set, inds, ordered_fields, starting_i, add_attn_check)
                    starting_i += len(cur_ad_set)
            
            # Set random order
            order = []
            for i in range(n_total):
                order.extend(ordered_fields[i])
            self.order_fields(order)
        
        # Pre-populate form
        if "initial" in kwargs.keys():
            initial = kwargs["initial"]
            for i in range(n_max):
                for prefix in ALL_PREFIXES:
                    # Fetch recorded form entries
                    k = f"{prefix}_ad_{i}_record_id"
                    if k in initial:
                        ad_record_id = initial[k]
                        if isinstance(ad_record_id, list):
                            ad_record_id = ad_record_id[0]
                        ad = ads_extension_models.AdRecord.objects.get(record_id=ad_record_id)
                        recall_ans = initial[f"{prefix}_ad_{i}_recall"]
                        rep_ans = initial[f"{prefix}_ad_{i}_rep"]
                        interest_ans = initial[f"{prefix}_ad_{i}_interest"]
                        ad_url = initial[f"{prefix}_ad_{i}_url"][0]
                        
                        # Pre-populate form fields
                        ind = i
                        self.fields[f"{prefix}_ad_{i}_recall"] = self.get_recall_field(ind, ad_url)
                        self.fields[f"{prefix}_ad_{i}_recall"].initial = recall_ans
                        self.fields[f"{prefix}_ad_{i}_rep"] = self.get_rep_field(ind)
                        self.fields[f"{prefix}_ad_{i}_rep"].initial = rep_ans
                        self.fields[f"{prefix}_ad_{i}_interest"] = self.get_interest_field(ind)
                        self.fields[f"{prefix}_ad_{i}_interest"].initial = interest_ans


class MidpointSurveyAdsSampleForm(SurveyAdsSampleForm):
    def __init__(self, ad_sets=None, n_max=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(ad_sets, n_max, *args, **kwargs)

class FinalSurveyAdsSampleForm(SurveyAdsSampleForm):
    def __init__(self, ad_sets=None, n_max=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(ad_sets, n_max, *args, **kwargs)


###### ADS LABELING FORM
class SurveyAdsLabelingForm(forms.Form):
    def get_ad_id_field(self, ad_record_id):
        return forms.CharField(
            label = "",
            widget = forms.TextInput(attrs = {'class': 'hidden'}),
            initial=ad_record_id,
            required=True,
        )

    def get_rep_field(self, i, ad_img_src):
        rep_question = f"Ad {i + 1}: To what extent do you feel represented by the highlighted individual in this ad image? <div><img src={ad_img_src} class='survey_ad_img'></div>"
        return forms.CharField(
            label=bold_label(rep_question),
            widget=forms.RadioSelect(choices=get_likert_choices("unrepresented", "represented")),
            required=True
        )
    
    def get_gender_field(self, i, ad_img_src):
        q = f"Ad {i + 1}: How do you perceive the gender of the highlighted individual? Select all categories that apply."
        return forms.MultipleChoiceField(
            label = bold_label(q),
            choices = [
                    ('W', 'Woman'),
                    ('M', 'Man'),
                    ('N', 'Non-binary'),
                    ('U', 'Unsure'),
                    ('textEntry', 'Free text:'),
                ],
            required = True,
            widget = forms.CheckboxSelectMultiple()
        )
    
    def get_race_field(self, i, ad_img_src):
        q = f"Ad {i + 1}: How do you perceive the race of the highlighted individual? Select all categories that apply."
        return forms.MultipleChoiceField(
            label = bold_label(q),
            choices = [
                    ('W', 'White'),
                    ('B', 'Black or African-American'),
                    ('N', 'American Indian or Alaskan Native'),
                    ('A', 'Asian or Asian-American'),
                    ('P', 'Native Hawaiian or Pacific Islander'),
                    ('O', 'Other'),
                    ('U', 'Unsure'),
                    ('textEntry', 'Free text:'),
                ],
            required = True,
            widget = forms.CheckboxSelectMultiple()
        )
    
    def get_ad_set(self, n):
        # Get first N ads in set
        file_path = os.path.join(settings.STATIC_ROOT, 'data/ads_for_labeling.pkl')
        with open(file_path, "rb") as f:
            img_filenames = pickle.load(f)
            return img_filenames[:n]

    def __init__(self, n, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)

        ads = self.get_ad_set(n)

        # Generate new form
        if "initial" not in kwargs.keys():
            inds = list(range(n))
            random.shuffle(inds)
            ordered_fields = {}
            for i, ad_name in enumerate(ads):
                # User ad
                ad_img_src = f"https://inadvertent-to-label.s3.us-west-2.amazonaws.com/{ad_name}"
                cur_ind = inds[i]
                self.fields[f"label_ad_{i}_record_id"] = self.get_ad_id_field(ad_name) # Hidden Ad ID field
                self.fields[f"label_ad_{i}_rep"] = self.get_rep_field(cur_ind, ad_img_src)
                self.fields[f"label_ad_{i}_gender"] = self.get_gender_field(cur_ind, ad_img_src)
                self.fields[f"label_ad_{i}_race"] = self.get_race_field(cur_ind, ad_img_src)
                ordered_fields[cur_ind] = [f"label_ad_{i}_record_id", f"label_ad_{i}_rep", f"label_ad_{i}_gender", f"label_ad_{i}_race"]
            
            # Set random order
            order = []
            for i in range(n):
                order.extend(ordered_fields[i])
            self.order_fields(order)
            
        # Pre-populate form
        elif "initial" in kwargs.keys():
            initial = kwargs["initial"]
            prefix = "label"
            for i in range(len(ads)):
                # Fetch recorded form entries
                record_id_key = f"{prefix}_ad_{i}_record_id"
                if record_id_key in initial:
                    ad_name = initial[record_id_key]
                    if isinstance(ad_name, list):
                        ad_name = ad_name[0]
                    ad_img_src = f"https://inadvertent-to-label.s3.us-west-2.amazonaws.com/{ad_name}"

                    rep_ans = initial[f"{prefix}_ad_{i}_rep"]
                    gender_ans = initial[f"{prefix}_ad_{i}_gender"]
                    race_ans = initial[f"{prefix}_ad_{i}_race"]
                    
                    # Pre-populate form fields
                    self.fields[f"{prefix}_ad_{i}_rep"] = self.get_rep_field(i, ad_img_src)
                    self.fields[f"{prefix}_ad_{i}_rep"].initial = rep_ans
                    self.fields[f"{prefix}_ad_{i}_gender"] = self.get_gender_field(i, ad_img_src)
                    self.fields[f"{prefix}_ad_{i}_gender"].initial = gender_ans
                    self.fields[f"{prefix}_ad_{i}_race"] = self.get_race_field(i, ad_img_src)
                    self.fields[f"{prefix}_ad_{i}_race"].initial = race_ans
 
class MidpointSurveyAdsLabelingForm(SurveyAdsLabelingForm):
    def __init__(self, n=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(n, *args, **kwargs)

class FinalSurveyAdsLabelingForm(SurveyAdsLabelingForm):
    def get_ad_set(self, n):
        # Get last N ads in set
        file_path = os.path.join(settings.STATIC_ROOT, 'data/ads_for_labeling.pkl')
        with open(file_path, "rb") as f:
            img_filenames = pickle.load(f)
            end = (n * 2)
            return img_filenames[n:end]

    def __init__(self, n=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(n, *args, **kwargs)


###### HOLISTIC AD LABELING FORM
class SurveyAdsHolisticForm(forms.Form):
    def get_ad_id_field(self, ad_record_ids):
        return forms.CharField(
            label = "",
            widget = forms.TextInput(attrs = {'class': 'hidden'}),
            initial=ad_record_ids,
            required=True,
        )
    def get_recall_field(self):
        recall_question = f"What proportion of the above ads do you recall seeing?"
        return forms.CharField(
            label=bold_label(recall_question),
            widget=forms.RadioSelect(choices=PCT_CHOICES),
            required=True
        )
    def get_rep_field(self):
        rep_question = f"Overall, to what extent do you feel like the above ads represent or resonate with you?"
        return forms.CharField(
            label=bold_label(rep_question),
            widget=forms.RadioSelect(choices=get_likert_choices("unrepresented", "represented")),
            required=True
        )
    def get_interest_field(self):
        interest_question = f"Overall, how interested are you in the products/opportunities shown in the ads shown above?"
        return forms.CharField(
            label=bold_label(interest_question),
            widget=forms.RadioSelect(choices=get_likert_choices("uninterested", "interested")),
            required=True
        )

    def __init__(self, ad_record_ids=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)

        self.fields["holistic_record_ids"] = self.get_ad_id_field(ad_record_ids)
        self.fields["holistic_recall"] = self.get_recall_field()
        self.fields["holistic_rep"] = self.get_rep_field()
        self.fields["holistic_interest"] = self.get_interest_field()

class MidpointSurveyAdsHolisticForm(SurveyAdsHolisticForm):
    def __init__(self, ad_cloud_link=None, ad_record_ids=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(ad_cloud_link, ad_record_ids, *args, **kwargs)

class FinalSurveyAdsHolisticForm(SurveyAdsHolisticForm):
    def __init__(self, ad_cloud_link=None, ad_record_ids=None, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(ad_cloud_link, ad_record_ids, *args, **kwargs)


# NEWS SURVEY FORMS
class IntroSurveyFormNews(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field(
                'politics_interest',
                'follow_politics',
                'social_media',
                'social_media_usage',
                'polarization',
                'agreement_policies',
                'attention_check',
                'your_view_public',
                'extreme_views',
                HTML("""<p>We'd like you to rate how you feel towards some groups on a scale of 0 to 100, where 0 means very unfavorable and 100 means very favorable. 50 means you do not feel favorable or unfavorable.</p>"""),
                'affective_polarization_dem',
                'affective_polarization_rep'
                )
        )
    politics_interest = forms.CharField(
        label=bold_label("How interested would you say you are in politics?"),
        widget=forms.RadioSelect(choices=[
            ("1", "Extremely interested"),
            ("2", "Very interested"),
            ("3", "Somewhat interested"),
            ("4", "Not very interested"),
            ("5", "Not at all interested")
        ]),
        required=True
    )
    follow_politics = forms.CharField(
        label=bold_label("How closely do you follow politics on TV, radio, newspapers, or the Internet?"),
        widget=forms.RadioSelect(choices=[
            ("1", "Extremely closely"),
            ("2", "Very closely"), 
            ("3", "Somewhat closely"),
            ("4", "Not very closely"),
            ("5", "Not at all")
        ]),
        required=True
    )

    social_media = forms.MultipleChoiceField(
        label=bold_label("Which of the following social media sites do you use on a regular basis (at least once a month)? Choose any that apply."),
        choices=[
            ('F', 'Facebook'),
            ('Y', 'YouTube'),
            ('T', 'Twitter (X)'),
            ('L', 'Linkedin'),
            ('R', 'Reddit'),
            ('I', 'Instagram'),
            ('K', 'TikTok'),
            ('O', 'Other'),
        ],
        required=True,
        widget=forms.CheckboxSelectMultiple()
    )

    social_media_usage = forms.CharField(
        label=bold_label("How often do you use Twitter (X)?"),
        widget=forms.RadioSelect(choices=[
            ("1", "Never"),
            ("2", "Less than once a month"),
            ("3", "Once or twice a month"),
            ("4", "Once a week"),
            ("5", "Several times a week"), 
            ("6", "Once a day"),
            ("7", "Multiple times a day")
        ]),
        required=True
    )

    polarization = forms.CharField(
        label=bold_label("How politically divided are Americans these days?"),
        widget=forms.RadioSelect(choices=[
            ("1", "Not at all divided"),
            ("2", "Not very divided"),
            ("3", "Somewhat divided"), 
            ("4", "Very divided"),
            ("5", "Extremely divided")
        ]),
        required=True
    )
    agreement_policies = forms.CharField(
        label=bold_label("How much agreement is there between the policies that Republican and Democratic voters want these days?"),
        widget=forms.RadioSelect(choices=[
            ('1', 'No agreement at all'),
            ('2', 'Very little agreement'),
            ('3', 'Some agreement'),
            ('4', 'A great deal of agreement'),
            ('5', 'Nearly all agreement')
        ]),
        required=True
    )
    attention_check = forms.CharField(
        label=bold_label("This is an attention check. Please select 'Strongly agree' to indicate you are paying attention to survey questions."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )
    your_view_public = forms.CharField(
        label=bold_label("Some people say the American public is extremely polarized politically these days, while others think this is not really true. Which statement best describes your view of the American public?"),
        widget=forms.RadioSelect(choices=[
            ('1', 'Americans are extremely polarized'),
            ('2', 'Americans are very polarized'),
            ('3', 'Americans are somewhat polarized'),
            ('4', 'Americans are not very polarized'),
            ('5', 'Americans are not at all polarized')
        ]),
        required=True
    )
    extreme_views = forms.CharField(
        label=bold_label('To what extent do you agree with the following statement? "More and more Americans have extreme views these days."'),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )
    affective_polarization_rep = forms.IntegerField(
        label=bold_label("Please rate your feelings towards those who support the <u>Republican</u> party"),
        widget=forms.NumberInput(attrs={'id': 'myRange1', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100', 'oninput': 'this.nextElementSibling.firstChild.value = this.value'}),
        help_text="<output>50</output>",
        required=True
    )
    affective_polarization_dem = forms.IntegerField(
        label=bold_label("Please rate your feelings towards those who support the <u>Democratic</u> party"),
        widget=forms.NumberInput(attrs={'id': 'myRange1', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100', 'oninput': 'this.nextElementSibling.firstChild.value = this.value'}),
        help_text="<output>50</output>",
        required=True
    )


class MidpointSurveyFormNews(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset("We'd like you to roughly estimate the ideological bias of the news on Twitter (X) on a 100-point scale for the past week. 0 means extremely liberal, 50 means ideologically neutral and 100 means extremely conservative.",
                'own_timeline',
                'overall_news',
                'rep_timeline',
                'dem_timeline',
            ),
            Fieldset("",
                     "overall_satisfied",
                     "news_satisfied",
                     "attention_check",
                     "news_credible",
                     "news_trust",
                     "neutral_algo",
                     "regulation"
                     ),
            Fieldset("", 
                    "recommend_content",
                    "prioritize_content",
                    "tailor_content",
                    "different_news"
                    ),
            Fieldset("Please read the following statements and select the choice that best describes yourself.",
                    "distorted", 
                    "harmful",
                    "slanted"
             )
        )

    own_timeline = forms.IntegerField(
        label=mark_safe("Recall the news on <b>your</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange1', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    overall_news = forms.IntegerField(
        label=mark_safe("<b>All news</b> available on Twitter (X) (including for you and other users) in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange2', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    rep_timeline = forms.IntegerField(
        label=mark_safe("News on a <b>typical conservative user's</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange3', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    dem_timeline = forms.IntegerField(
        label=mark_safe("News on a <b>typical liberal user's</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange4', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )

    overall_satisfied = forms.CharField(
        label=mark_safe("Thinking back on the last week, how satisfied are you with the <b>user experience</b> on on Twitter (X) overall?"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("unsatisfied", "satisfied")),
        required=True
    )

    news_satisfied = forms.CharField(
        label=mark_safe("How satisfied are you with the <b>news environment</b> on Twitter (X) in the last week?"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("unsatisfied", "satisfied")),
        required=True
    )

    attention_check = forms.CharField(
        label=mark_safe("This is an attention check. Please select 'Somewhat agree' to indicate you are paying attention to survey questions."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    CREDIBLE_CHOICES = [
        ("1", "Extremely high credibility"),
        ("2", "Somewhat high credibility"),
        ("3", "Neither credible nor  untrustworthy"),
        ("4", "Somewhat low credibility"),
        ("5", "Extremely low credibility"),
    ]

    news_credible = forms.CharField(
        label=mark_safe("Please estimate the credibility of the news information you see on Twitter (X):"),
        widget=forms.RadioSelect(choices=CREDIBLE_CHOICES),
        required=True
    )

    news_trust = forms.CharField(
        label=mark_safe("Please indicate the extent to which you trust the <b>news information</b> you see on Twitter (X):"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("distrust", "trust")),
        required=True
    )

    SOCIAL_MEDIA_PERCEPTION_CHOICES = [
        ("1", "Primarily supports liberals' posts"),
        ("2", "Somewhat supports liberals' posts"),
        ("3", "Generally neutral"),
        ("4", "Somewhat supports conservatives' posts"),
        ("5", "Primarily supports conservatives' posts")
    ]

    neutral_algo = forms.CharField(
        label=mark_safe("Do you think the Twitter (X) algorithm is generally neutral, or primarily supports posts from liberals or conservatives?"),
        widget=forms.RadioSelect(choices=SOCIAL_MEDIA_PERCEPTION_CHOICES),
        required=True
    )

    regulation = forms.CharField(
        label=mark_safe("To what extent do you agree with the following statement: There should be more government regulation of social media companies like Twitter (X)"),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )
    AWARENESS_CHOICES = [
        ("1", "Not at all aware"), 
        ("2", "Slightly aware"), 
        ("3", "Moderately aware"), 
        ("4", "Very aware"),
        ("5", "Completely aware"), 
    ]

    recommend_content = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to recommend content to the user on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    prioritize_content = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to prioritize certain content above others on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    tailor_content = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to tailor certain content to the user on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    different_news = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to show someone else different news than you get to see on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    distorted = forms.CharField(
        label=mark_safe("Most news online is distorted by social media algorithms."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    harmful = forms.CharField(
        label=mark_safe("News delivered through social media algorithms is harmful to democracy."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    slanted = forms.CharField(
        label=mark_safe("Social media algorithms deliver news that tends to be slanted against my views."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )


class SecondMidpointSurveyFormNews(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset("We'd like you to roughly estimate the ideological bias of the news on Twitter (X) on a 100-point scale for the past week. 0 means extremely liberal, 50 means ideologically neutral and 100 means extremely conservative.",
                'own_timeline',
                'overall_news',
                'rep_timeline',
                'dem_timeline',
            ),
            Fieldset("",
                     "overall_satisfied",
                     "news_satisfied",
                     "attention_check",
                     "news_credible",
                     "news_trust",
                     "neutral_algo",
                     "regulation"
                     ),
        )

    own_timeline = forms.IntegerField(
        label=mark_safe("Recall the news on <b>your</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange1', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    overall_news = forms.IntegerField(
        label=mark_safe("<b>All news</b> available on Twitter (X) (including for you and other users) in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange2', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    rep_timeline = forms.IntegerField(
        label=mark_safe("News on a <b>typical conservative user's</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange3', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    dem_timeline = forms.IntegerField(
        label=mark_safe("News on a <b>typical liberal user's</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange4', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )

    overall_satisfied = forms.CharField(
        label=mark_safe("Thinking back on the last week, how satisfied are you with the <b>user experience</b> on on Twitter (X) overall?"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("unsatisfied", "satisfied")),
        required=True
    )

    news_satisfied = forms.CharField(
        label=mark_safe("How satisfied are you with the <b>news environment</b> on Twitter (X) in the last week?"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("unsatisfied", "satisfied")),
        required=True
    )

    attention_check = forms.CharField(
        label=mark_safe("This is an attention check. Please select 'Somewhat agree' to indicate you are paying attention to survey questions."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    CREDIBLE_CHOICES = [
        ("1", "Extremely high credibility"),
        ("2", "Somewhat high credibility"),
        ("3", "Neither credible nor  untrustworthy"),
        ("4", "Somewhat low credibility"),
        ("5", "Extremely low credibility"),
    ]

    news_credible = forms.CharField(
        label=mark_safe("Please estimate the credibility of the news information you see on Twitter (X):"),
        widget=forms.RadioSelect(choices=CREDIBLE_CHOICES),
        required=True
    )

    news_trust = forms.CharField(
        label=mark_safe("Please indicate the extent to which you trust the <b>news information</b> you see on Twitter (X):"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("distrust", "trust")),
        required=True
    )

    SOCIAL_MEDIA_PERCEPTION_CHOICES = [
        ("1", "Primarily supports liberals' posts"),
        ("2", "Somewhat supports liberals' posts"),
        ("3", "Generally neutral"),
        ("4", "Somewhat supports conservatives' posts"),
        ("5", "Primarily supports conservatives' posts")
    ]

    neutral_algo = forms.CharField(
        label=mark_safe("Do you think the Twitter (X) algorithm is generally neutral, or primarily supports posts from liberals or conservatives?"),
        widget=forms.RadioSelect(choices=SOCIAL_MEDIA_PERCEPTION_CHOICES),
        required=True
    )

    regulation = forms.CharField(
        label=mark_safe("To what extent do you agree with the following statement: There should be more government regulation of social media companies like Twitter (X)"),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )


class FinalSurveyFormNews(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset("We'd like you to roughly estimate the ideological bias of the news on Twitter (X) on a 100-point scale for the past week. 0 means extremely liberal, 50 means ideologically neutral and 100 means extremely conservative.",
                'own_timeline',
                'overall_news',
                'rep_timeline',
                'dem_timeline',
            ),
            Fieldset("",
                     "overall_satisfied",
                     "news_satisfied",
                     "attention_check",
                     "news_credible",
                     "news_trust",
                     ),
            Fieldset("", 
                     "neutral_algo",
                     "regulation",
                     ),
            Fieldset("", 
                    "recommend_content",
                    "prioritize_content",
                    "tailor_content",
                    "different_news"
                    ),
            Fieldset("Please read the following statements and select the choice that best describes yourself.",
                    "distorted", 
                    "harmful",
                    "slanted"
             )
        )

    own_timeline = forms.IntegerField(
        label=mark_safe("Recall the news on <b>your</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange1', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    overall_news = forms.IntegerField(
        label=mark_safe("<b>All news</b> available on Twitter (X) (including for you and other users) in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange2', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    rep_timeline = forms.IntegerField(
        label=mark_safe("News on a <b>typical conservative user's</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange3', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )
    dem_timeline = forms.IntegerField(
        label=mark_safe("News on a <b>typical liberal user's</b> Twitter (X) timeline in the past week:"),
        widget=forms.NumberInput(attrs={'id': 'myRange4', 'class': 'slider', 'type': 'range', 'step': '1', 'min': '0', 'max': '100'}),
        required=True
    )

    overall_satisfied = forms.CharField(
        label=mark_safe("Thinking back on the last week, how satisfied are you with the <b>user experience</b> on on Twitter (X) overall?"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("unsatisfied", "satisfied")),
        required=True
    )

    news_satisfied = forms.CharField(
        label=mark_safe("How satisfied are you with the <b>news environment</b> on Twitter (X) in the last week?"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("unsatisfied", "satisfied")),
        required=True
    )

    attention_check = forms.CharField(
        label=mark_safe("This is an attention check. Please select 'Neither agree nor disagree' to indicate you are paying attention to survey questions."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    CREDIBLE_CHOICES = [
        ("1", "Extremely high credibility"),
        ("2", "Somewhat high credibility"),
        ("3", "Neither credible nor  untrustworthy"),
        ("4", "Somewhat low credibility"),
        ("5", "Extremely low credibility"),
    ]

    news_credible = forms.CharField(
        label=mark_safe("Please estimate the credibility of the news information you see on Twitter (X):"),
        widget=forms.RadioSelect(choices=CREDIBLE_CHOICES),
        required=True
    )

    news_trust = forms.CharField(
        label=mark_safe("Please indicate the extent to which you trust the news information you see on Twitter (X):"),
        widget=forms.RadioSelect(choices=get_5_point_likert_choices("distrust", "trust")),
        required=True
    )

    SOCIAL_MEDIA_PERCEPTION_CHOICES = [
        ("1", "Primarily supports liberals' posts"),
        ("2", "Somewhat supports liberals' posts"),
        ("3", "Generally neutral"),
        ("4", "Somewhat supports conservatives' posts"),
        ("5", "Primarily supports conservatives' posts")
    ]


    neutral_algo = forms.CharField(
        label=mark_safe("Do you think the Twitter (X) algorithm is generally neutral, or primarily supports posts from liberals or conservatives?"),
        widget=forms.RadioSelect(choices=SOCIAL_MEDIA_PERCEPTION_CHOICES),
        required=True
    )

    regulation = forms.CharField(
        label=mark_safe("To what extent do you agree with the following statement: There should be more government regulation of social media companies like Twitter (X)"),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    AWARENESS_CHOICES = [
        ("1", "Not at all aware"), 
        ("2", "Slightly aware"), 
        ("3", "Moderately aware"), 
        ("4", "Very aware"),
        ("5", "Completely aware"), 
    ]

    recommend_content = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to recommend content to the user on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    prioritize_content = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to prioritize certain content above others on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    tailor_content = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to tailor certain content to the user on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    different_news = forms.CharField(
        label=mark_safe("To what extent are you aware that algorithms are used to show someone else different news than you get to see on social media?"),
        widget=forms.RadioSelect(choices=AWARENESS_CHOICES),
        required=True
    )

    distorted = forms.CharField(
        label=mark_safe("Most news online is distorted by social media algorithms."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    harmful = forms.CharField(
        label=mark_safe("News delivered through social media algorithms is harmful to democracy."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )

    slanted = forms.CharField(
        label=mark_safe("Social media algorithms deliver news that tends to be slanted against my views."),
        widget=forms.RadioSelect(choices=AGREEMENT_CHOICES),
        required=True
    )