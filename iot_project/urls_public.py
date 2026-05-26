"""
Public-schema URLs. Served when no X-Tenant-ID header is provided
(admin, auth-token issuance, tenant management).
"""
from django.contrib import admin
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-token-auth/', obtain_auth_token),
]
