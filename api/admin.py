"""api admin"""
from django.contrib import admin
from .models import Song, Chart, Pack, ChartData

admin.site.register(Pack)
admin.site.register(Song)
admin.site.register(Chart)
admin.site.register(ChartData)
