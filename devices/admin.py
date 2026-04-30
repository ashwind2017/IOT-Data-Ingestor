from django.contrib import admin

from .models import Device, Payload


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('devEUI', 'latest_status', 'created_at')
    search_fields = ('devEUI',)


@admin.register(Payload)
class PayloadAdmin(admin.ModelAdmin):
    list_display = ('device', 'fCnt', 'status', 'received_at')
    list_filter = ('status',)
    search_fields = ('device__devEUI',)
