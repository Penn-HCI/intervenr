from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from onboard.models import Demographics, ZipCodeInfo


class InformedConsentForm(forms.Form):
    us_residency = forms.BooleanField(label="I am living in the United States.", required=True)
    age_eligible = forms.BooleanField(label="I am 18 years old or older.", required=True)
    main_browser = forms.BooleanField(label="My main web browser is Google Chrome.", required=True)
    informed_consent = forms.BooleanField(label="I have read the above information and consent to participate.", required=True)
    prolific_id = forms.CharField(label="Please enter your 24 character Prolific ID.", max_length=24, required=True, 
                                  validators=[
                                    validators.MinLengthValidator(24), 
                                    validators.RegexValidator(
                                        regex='^[a-zA-Z0-9]*$',
                                        message='Prolific Id must be Alphanumeric',
                                        code='invalid_prolific_id'
                                    )]
                                )

class OnboardForm(forms.Form):
    onboard_code = forms.CharField(label="Please enter your 6 character registration code.", max_length=6, required=True)

# Zip Code Validator
def validate_zipcode(value):
    # If zip code explicitly not in database, raise error
    if ZipCodeInfo.objects.filter(zip=value).count() == 0:
        raise ValidationError(
            ('%(value)s is not a valid zip code.'),
            code='ZipCodeDNE',
            params={'value': value}
        )

class DemographicsForm(forms.ModelForm):
    race_multi_list = forms.MultipleChoiceField(
        label =  'What is your racial identity? Select all categories that apply.',
        choices = [
                ('W', 'White'),
                ('B', 'Black or African-American'),
                ('A', 'Asian or Asian-American'),
                ('H', 'Hispanic or Latino'),
                ('N', 'Native American'),
                ('O', 'Other'),
            ],
        required = True,
        widget = forms.CheckboxSelectMultiple()
    )
    zipcode = forms.CharField(
        label = 'What is your 5 digit zip code?',
        max_length = 5,
        min_length = 5,
        validators = [validate_zipcode],
        widget = forms.TextInput(attrs = {'placeholder': 'Type zip code here...'}),
        required = True,
    )

    class Meta:
        model = Demographics
        fields = [
            'state', 'zipcode','age', 'gender', 'education',
            'household_income', 'pol_ideology', 'pol_scale', 'past_voting'
        ]
        widgets = {
            'age': forms.RadioSelect(),
            'gender': forms.RadioSelect(),
            'state': forms.Select(),
            'education': forms.RadioSelect(),
            'household_income': forms.RadioSelect(),
            'pol_ideology': forms.RadioSelect(),
            'pol_scale': forms.RadioSelect(),
            'past_voting': forms.RadioSelect(),
        }
        labels = {
            'age': 'What is your age?',
            'gender': 'What is your gender identity?',
            'state': 'What U.S. state or territory are you in?',
            'education': 'What is the highest level of education you have completed or are currently completing?',
            'household_income': 'What is your household\'s annual income?',
            'pol_ideology': 'Generally speaking, do you usually think of yourself as a ...',
            'pol_scale': 'Where would you place yourself on this scale?',
            'past_voting': 'Of the previous U.S. elections you\'ve been eligible to vote in, approximately how many have you voted in?',
        }


class ExtensionForm(forms.Form):
    user_id = forms.CharField(
        label = "",
        max_length = 36,
        min_length = 36,
        widget = forms.TextInput(attrs = {'class': 'hidden'}),
        required = False,
    )
    experiment_type = forms.IntegerField(
        label="", 
        widget=forms.TextInput(attrs = {'class': 'hidden'}), 
        required=False,
    )
    is_admin = forms.BooleanField(
        label="",
        widget=forms.TextInput(attrs = {'class': 'hidden'}), 
        required=False,
    )
