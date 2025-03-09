"""Api urls"""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.hello_api, name='hello_api'),
]
