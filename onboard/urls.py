from django.urls import path
from onboard import views


app_name = 'onboard'


urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    #path('demographics/', views.DemographicsView.as_view(), name='demographics'),
    path('install/', views.InstallView.as_view(), name='install'),
    path('extension/', views.ExtensionView.as_view(), name='extension'),
    path('complete/', views.CompleteView.as_view(), name='complete'),
    path('redirect/', views.RedirectView.as_view(), name='redirect'),

    # Prolific paths
    path('prolific/', views.IndexProlificView.as_view(), name='index_prolific'),
    path('demographics_prolific/', views.DemographicsProlificView.as_view(), name='demographics_prolific'),
    path('extension_prolific/', views.ExtensionProlificView.as_view(), name='extension_prolific'),
    path('complete_prolific/', views.CompleteProlificView.as_view(), name='complete_prolific'),
    path('redirect_prolific/', views.RedirectProlificView.as_view(), name='redirect_prolific'),

    path('extension-download/', views.extension_download, name='extension-download'),
    path('start_onboard/', views.StartOnboardView.as_view(), name='start_onboard'),
    path('pre_onboard/', views.PreOnboardView.as_view(), name='pre_onboard'),
]
