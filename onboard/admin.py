from django.contrib import admin
from onboard import models

# Register your models here.
admin.site.register(models.Demographics)
admin.site.register(models.OnboardCode)
admin.site.register(models.ZipCodeInfo)
admin.site.register(models.ProlificId)