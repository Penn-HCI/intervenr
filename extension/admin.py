from django.contrib import admin
from extension import models

# Register your models here.
admin.site.register(models.UrlRecord)
admin.site.register(models.URLMetadata)
admin.site.register(models.DailyInterventionCount)
admin.site.register(models.DailyVisibleLinkCount)
admin.site.register(models.VisibleLinkRecord)
admin.site.register(models.VisibleLinkMetadata)
admin.site.register(models.TldRecord)
admin.site.register(models.ExtensionAlert)
admin.site.register(models.ExtensionError)
admin.site.register(models.TweetRecord)
admin.site.register(models.TweetMetadata)