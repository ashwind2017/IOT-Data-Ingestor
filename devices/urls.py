from django.urls import path

from . import views

urlpatterns = [
    path('payloads/', views.create_payload, name='create_payload'),
]
