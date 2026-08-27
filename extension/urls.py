from django.urls import path
from extension import views


app_name = 'extension'


urlpatterns = [
    path('start-url/', views.StartUrlView.as_view(), name='start-url'),
    path('end-url/', views.EndUrlView.as_view(), name='end-url'),
    path('action/', views.ActionView.as_view(), name='action'),
    path('update/', views.UpdateView.as_view(), name='update'),
    path('collect-links/', views.CollectLinksView.as_view(), name='collect-links'),
    path('collect-tweets/', views.CollectTweetsView.as_view(), name='collect-tweets'),
    path('collect-tweet-visible-duration/', views.CollectTweetVisibleDurationView.as_view(), name='collect-tweet-visible-duration'),
    path('collect-visible-link-duration/', views.CollectVisibleLinkDurationView.as_view(), name='collect-visible-link-duration'),
    path('collect-tweet-engagements/', views.CollectTweetEngagementsView.as_view(), name='collect-tweet-engagements'),
]
