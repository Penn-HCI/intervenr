from django.contrib import admin
from frontend.models import ExperimentMember, IntroSurvey, MidpointSurvey, SecondMidpointSurvey, FinalSurvey, ExperimentSettings

# Register your models here.
class ExperimentMemberAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'creation_date', 'contact_email', 'experiment_type', 'has_onboard_permission', 'has_onboarded', 'offboard_user')
    search_fields = ['user_id', 'contact_email']

class ExperimentSettingsAdmin(admin.ModelAdmin):
    list_display = ('creation_date', 'exp_name', 'obs_start', 'obs_end', 'interv_start', 'interv_end')

admin.site.register(ExperimentMember, ExperimentMemberAdmin)
admin.site.register(IntroSurvey)
admin.site.register(MidpointSurvey)
admin.site.register(SecondMidpointSurvey)
admin.site.register(FinalSurvey)
admin.site.register(ExperimentSettings, ExperimentSettingsAdmin)