from django.contrib import admin
from .models import Song, Chart, Pack

admin.site.register(Pack)
admin.site.register(Song)
admin.site.register(Chart)