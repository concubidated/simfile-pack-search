"""Api urls"""
from django.urls import path

from . import views

urlpatterns = [
    path('packs', views.pack_list),
    path('chart/<int:chart_id>', views.chart_json),
    path('chart/key/<str:chart_key>', views.chart_json_by_key),
]
