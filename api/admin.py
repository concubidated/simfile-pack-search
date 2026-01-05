"""api admin"""
from django import forms
from django.shortcuts import render, redirect
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpRequest
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.urls import path
from django_q.tasks import async_task

from .models import ScanPacksRun, Song, Chart, Pack, ChartData
from .utils.rename_pack import rename_pack_file

admin.site.register(ChartData)

@admin.register(ScanPacksRun)
class ScanPacksRunAdmin(admin.ModelAdmin):
    """Admin interface for Scanning Packs"""
    change_list_template = "admin/scanpacksrun/change_list.html"

    class Media:
        css = {"all": ("admin/css/scanpacksruns.css",)}

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "run/<str:packdir>/",
                self.admin_site.admin_view(self.run_scan_view),
                name="scanpacksrun_run",
            ),
        ] + urls

    @method_decorator(require_POST)
    def run_scan_view(self, request, packdir: str):
        """View for the scan run"""
        changelist_url = "admin:api_scanpacksrun_changelist"

        try:
            run = ScanPacksRun.objects.create(packdir=packdir, created_by=request.user)
        except IntegrityError:
            messages.warning(request, f"A {packdir} scan is already queued/running.")
            return redirect(changelist_url)

        task_id = async_task("api.tasks.scan_packs_task", run.id)
        run.q_task_id = task_id or ""
        run.save(update_fields=["q_task_id"])

        messages.success(request, f"Queued scan_packs {packdir} (run #{run.id}).")
        return redirect(changelist_url)

    def has_add_permission(self, request):
        return False

class NoCountPaginator(Paginator):
    """Paginator that avoids COUNT(*) on very large tables."""

    def count(self):
        # Don't hit the DB for COUNT(*); return a big dummy value instead.
        # Admin will still work; total pages just won't be exact.
        return 999999

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
    ordering = ("-id",)
    search_fields = ("name", "altname")
    list_filter = ("sync", "date_created",)
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

class ChartInline(admin.TabularInline):
    """Chart Inline"""
    model = Chart
    extra = 0
    fields = ("charttype", "difficulty", "meter", "author")

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    """Admin interface for Songs"""
    list_display = ("title", "artist", "pack_name",)
    ordering = ("-title",)
    search_fields = ("title","artist",)
    inlines = [ChartInline]

    list_select_related = ("pack",)
    # Key line:
    autocomplete_fields = ("pack",)

    def pack_name(self, obj):
        """Returns the name of the pack associated with the song."""
        return obj.pack.name
    pack_name.admin_order_field = "pack__name"

@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    """Admin interface for Charts"""

    list_display = ("song_title", "pack_name", "charttype", "difficulty", "meter")
    search_fields = ("song__title",)

    list_filter = ("charttype",)
    list_select_related = ("song", "song__pack")
    ordering = ("-id",)
    list_per_page = 50

    paginator = NoCountPaginator
    show_full_result_count = False  # tiny extra perf win

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("song")

        rm = getattr(request, "resolver_match", None)
        is_changelist = rm and rm.url_name.endswith("_changelist")

        if is_changelist and not request.GET.get("q"):
            # No search yet -> show nothing, just the search box
            return qs.none()
        return qs

    def song_title(self, obj):
        """Returns the song title"""
        return obj.song.title

    song_title.admin_order_field = "song__title"

    def pack_name(self, obj):
        """Returns the pack Name"""
        pack = getattr(obj.song, "pack", None)
        return pack.name if pack else "—"

    pack_name.admin_order_field = "song__pack__name"
