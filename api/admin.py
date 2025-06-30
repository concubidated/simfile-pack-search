"""api admin"""
from django import forms
from django.shortcuts import render, redirect
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db.models import Count
from .models import Song, Chart, Pack, ChartData
from .utils.rename_pack import rename_pack_file

admin.site.register(ChartData)

class RenamePacksForm(forms.Form):
    """Form for renaming packs."""
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    new_name = forms.CharField(
        max_length=255,
        required=True,
        help_text="Enter the new name to apply to selected packs."
    )

def rename_packs_action(_, request, queryset):
    """Action to rename selected packs."""
    form = None

    if queryset.count() != 1:
        messages.error(request, "Please select exactly one pack to rename at a time.")
        return redirect(request.get_full_path())

    if 'apply' in request.POST:
        form = RenamePacksForm(request.POST)
        if form.is_valid():
            new_name = form.cleaned_data['new_name']
            selected_ids = request.POST.getlist('_selected_action')

            for pack in Pack.objects.filter(id__in=selected_ids):
                old_name = pack.name
                zip_path = f"/data/packs/{pack.name}.zip"

                try:
                    rename_pack_file(zip_path, old_name, new_name)
                    pack.name = new_name
                    pack.save()
                    messages.success(request, f"Renamed '{old_name}' to '{new_name}'")
                except Exception as e:
                    messages.error(request, f"Error renaming '{old_name}': {e}")

            return redirect(request.get_full_path())

    if not form:
        form = RenamePacksForm(
            initial={'_selected_action': request.POST.getlist(ACTION_CHECKBOX_NAME)})

    return render(request, 'admin/rename_pack.html', context={
        'packs': queryset,
        'rename_form': form,
        'title': 'Rename Selected Packs'
    })

@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    """Admin interface for Packs"""
    list_display = ("name", "date_scanned", "date_created", "song_count", "downloads")
    ordering = ("-name",)
    search_fields = ("name",)
    list_filter = ("date_created",)
    actions = [rename_packs_action]

    def get_queryset(self, request):
        """Annotate the queryset with the song count."""
        qs = super().get_queryset(request)
        return qs.annotate(song_count=Count("songs"))

    def song_count(self, obj):
        """Returns the number of songs in the pack."""
        return obj.song_count
    song_count.admin_order_field = "song_count"
    song_count.short_description = "Songs"

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    """Admin interface for Songs"""
    list_display = ("title", "artist", "pack_name",)
    ordering = ("-title",)
    search_fields = ("title","artist",)

    def pack_name(self, obj):
        """Returns the name of the pack associated with the song."""
        return obj.pack.name
    pack_name.admin_order_field = "pack__name"

@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    """Admin interface for Charts"""
    list_display = ("song_title", "pack_name", "charttype", "meter")
    ordering = ("-song__title",)
    search_fields = ("song__title",)
    list_filter = ("charttype",)

    def song_title(self, obj):
        """Returns the title of the song associated with the chart."""
        return obj.song.title
    song_title.admin_order_field = "song__title"

    def pack_name(self, obj):
        """Returns the name of the pack associated with the song."""
        return obj.song.pack.name
    pack_name.admin_order_field = "song__pack__name"
