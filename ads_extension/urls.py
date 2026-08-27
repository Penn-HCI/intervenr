from django.urls import path
from ads_extension import views

app_name = "ads_extension"

urlpatterns = [
    path('action/', views.ActionView.as_view(), name='action'),
    path('update/', views.UpdateView.as_view(), name='update'),
    path('qualtrics/', views.QualtricsView.as_view(), name='qualtrics'),
    path('collect-ads/', views.CollectAdsView.as_view(), name='collect-ads'),
    path('collect-seen-ads/', views.CollectSeenAdsView.as_view(), name='collect-seen-ads'),
    path('collect-clicked-ads/', views.CollectClickedAdsView.as_view(), name='collect-clicked-ads'),
]