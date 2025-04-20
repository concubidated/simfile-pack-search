"""api admin"""
from django.contrib import admin
from django.db.models import Count
from .models import Song, Chart, Pack, ChartData

admin.site.register(ChartData)

@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = ("name", "date_scanned", "date_created", "song_count", "downloads")
    ordering = ("-name",)
    search_fields = ("name",)
    list_filter = ("date_created",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(song_count=Count("songs"))

    def song_count(self, obj):
        return obj.song_count
    song_count.admin_order_field = "song_count"
    song_count.short_description = "Songs"

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ("title", "artist", "pack_name",)
    ordering = ("-title",)
    search_fields = ("title","artist",)

    def pack_name(self, obj):
        return obj.pack.name
    pack_name.admin_order_field = "pack__name"

@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = ("song_title", "pack_name", "charttype", "meter")
    ordering = ("-song__title",)
    search_fields = ("song__title",)
    list_filter = ("charttype",)

    def song_title(self, obj):
        return obj.song.title
    song_title.admin_order_field = "song__title"

    def pack_name(self, obj):
        return obj.song.pack.name
    pack_name.admin_order_field = "song__pack__name"