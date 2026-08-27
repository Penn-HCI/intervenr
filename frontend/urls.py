from django.urls import path
from frontend import views


app_name = 'frontend'


urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('user-del-url', views.UserDeleteUrlRecord.as_view(), name='user-del-url'),
    path('user-del-ad', views.UserDeleteAdRecord.as_view(), name='user-del-ad'),
    path('user-update-email', views.UserUpdateEmail.as_view(), name='user-update-email'),
    path('simple-admin', views.SimpleAdmin.as_view(), name='simple-admin'),
    path('dashboard/', views.Dashboard.as_view(), name='dashboard'),
    path('analysis-dashboard', views.AnalysisDashboard.as_view(), name='analysis-dashboard'),
    path('dl-participants', views.SADownloadParticipants.as_view(), name='dl-participants'),
    path('dl-url-records', views.SADownloadUrlRecords.as_view(), name='dl-url-records'),
    path('dl-intervention-cnts', views.SADownloadInterventionCounts.as_view(), name='dl-intervention-cnts'),
    path('dl-visible-links', views.SADownloadVisibleLinkRecords.as_view(), name='dl-visible-links'),
    path('sa-assign-pairs', views.SAAssignPairs.as_view(), name='sa-assign-pairs'),
    path('sa-reset-tlds', views.SAResetTlds.as_view(), name='sa-reset-tlds'),
    path('sa-assign-intervention-groups', views.SAInterventionGroups.as_view(), name='sa-assign-intervention-groups'),
    path('sa-add-onboard-codes', views.SAOnboardCodes.as_view(), name='sa-add-onboard-codes'),
    path('sa-offboard-users', views.SAOffboardUsers.as_view(), name='sa-offboard-users'),
    path('sa-mass-action', views.SAMassAction.as_view(), name='sa-mass-action'),
    path('intro-survey/', views.IntroSurveyNews.as_view(), name='intro-survey'),
    path('midpoint-survey/', views.MidpointSurveyNews.as_view(), name='midpoint-survey'),
    path('checkin-survey/', views.SecondMidpointSurveyNews.as_view(), name='checkin-survey'),
    path('final-survey/', views.FinalSurveyNews.as_view(), name='final-survey'),
    path('mass-offboard-users/', views.MassOffboardUsers.as_view(), name='mass-offboard-users'),
    path('grant-onboard-perm/', views.GrantOnboardPermission.as_view(), name='grant-onboard-perm'),
    path('revoke-onboard-perm/', views.RevokeOnboardPermission.as_view(), name='revoke-onboard-perm'),
    path('start/', views.start, name='start'),
    path('privacy/', views.privacy, name='privacy'),
    path('about/', views.about, name='about'),
    path('logout/', views.logout_view, name='logout'),
]
