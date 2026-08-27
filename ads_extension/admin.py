from django.contrib import admin
from ads_extension import models

# Register your models here.
class AdRecordAdmin(admin.ModelAdmin):
    list_display = ('participant_id', 'record_id', 'created_time', 'content_type', 'intervenr_ad_type', 'src_page_title', 'page_domain', 'img_preview', 'img_was_downloaded', 'src_page_url', 'target_domain', 'target_hostname', 'original_ad', 'target_url', 'img_src')

    def img_preview(self, obj):
        return obj.img_preview
    
    img_preview.short_description = "Image Preview"
    img_preview.allow_tags = True

class AdRecordRedactionAdmin(admin.ModelAdmin):
    list_display = ('participant_id', 'n_deleted', 'created_time')

class ClientIPAdmin(admin.ModelAdmin):
    list_display = ('participant_id', 'ip', 'created_time')

admin.site.register(models.AdRecord, AdRecordAdmin)
admin.site.register(models.AdMetadata)
admin.site.register(models.ExtensionAlert)
admin.site.register(models.ExtensionError)
admin.site.register(models.AdRecordRedaction, AdRecordRedactionAdmin)
admin.site.register(models.ClientIP, ClientIPAdmin)
