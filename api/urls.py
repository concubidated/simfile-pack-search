"""Api urls"""
from django.urls import path

from . import views

urlpatterns = [
    path('packs', views.pack_list),
]
