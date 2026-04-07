"""Api urls"""
from django.urls import path

from web.views import pack_list_datatables

from . import views

urlpatterns = [
    path('packs/datatables', pack_list_datatables, name='pack_list_datatables'),
    path('packs', views.pack_list),
    path('chart/<int:chart_id>', views.chart_json),
    path('chart/key/<str:chart_key>', views.chart_json_by_key),
    path('search/', views.search)
]
