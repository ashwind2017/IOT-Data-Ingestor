"""
Tenant-scoped URL configuration.

Requests with an `X-Tenant-ID` header are routed here. All endpoints
under /api/ hit the per-tenant Postgres schema.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('devices.urls')),
]
