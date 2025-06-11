"""Api urls"""
from django.urls import path

from . import views

urlpatterns = [
    path('packs', views.pack_list),
    path('chart/<int:chart_id>', views.chart_json),
]
