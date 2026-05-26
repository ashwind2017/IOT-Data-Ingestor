from django.urls import path

from . import views

urlpatterns = [
    path('payloads/', views.create_payload, name='create_payload'),
    path('payloads/bulk/', views.create_payloads_bulk, name='create_payloads_bulk'),
    path('payloads/upload/', views.upload_payloads_file, name='upload_payloads_file'),
    path('payloads/stream/', views.stream_payloads, name='stream_payloads'),
]
