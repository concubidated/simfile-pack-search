"""web views"""
import re
import os
import json
import string
from collections import OrderedDict
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.db.models import Prefetch, Min, Max, Count, F, Value

from api.models import Pack, Song, Chart, ChartData

def natural_sort_key(text):
    """we are hoomans, lets sort like it"""
    # Determine top-level priority based on first character
    first_char = text.lstrip()[0] if text.strip() else ''
    if first_char in string.ascii_letters:
        priority = 2
    elif first_char.isdigit():
        priority = 1
    else:
        priority = 0

    # Split text into alphanumeric chunks for natural sorting
    parts = re.split(r'(\d+)', text)
    normalized = [
        int(part) if part.isdigit() else part.lower()
        for part in parts
    ]

    return (priority, normalized)

def download_pack(request, pack_id):
    """wrapper for downloading packs"""
    pack = get_object_or_404(Pack, id=pack_id)

    file_name = f"{pack.name}.zip"

    Pack.objects.filter(id=pack_id).update(downloads=F('downloads') + 1)
    response = HttpResponse()
    response["X-Accel-Redirect"] = f"/packs/{file_name}"
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["Content-Type"] = ""
    return response

def download_mirror(request, pack_id):
    """wrapper for downloading from the mirror"""
    pack = get_object_or_404(Pack, id=pack_id)
    base_url = os.environ.get("MIRROR_BASE_URL")
    if not base_url:
        return HttpResponse("Error: Mirror URL Not Set")

    file_name = f"{pack.name}.zip"
    redirect_url = base_url.rstrip("/") + "/" + os.path.basename(file_name)
    Pack.objects.filter(id=pack_id).update(downloads=F('downloads') + 1)
    return HttpResponseRedirect(redirect_url)

def search(request, search_type=None, search_query=None):
    """search for a song"""
    if not search_type or not search_query:
        search_type = request.POST.get("type")
        search_query = request.POST.get("search")
        return redirect(f"/search/{search_type}/{search_query}")

    valid_types = ["title", "artist", "credit", "pack"]
    if search_type not in valid_types:
        return redirect("/")

    charts_qs = Chart.objects.only("meter", "difficulty", "charttype", "song_id")
    songs = None
    if "title" in search_type:
        songs = (
            Song.objects.prefetch_related(
                Prefetch("charts", queryset=charts_qs)
            )
            .select_related("pack")
            .annotate(
                min_meter=Min("charts__meter"),
                max_meter=Max("charts__meter")
            )
            .filter(title__icontains=search_query))
    elif "artist" in search_type:
        songs = (
            Song.objects.prefetch_related(
                Prefetch("charts", queryset=charts_qs)
            )
            .select_related("pack")
            .annotate(
                min_meter=Min("charts__meter"),
                max_meter=Max("charts__meter")
            )
            .filter(artist__icontains=search_query))
    elif "credit" in search_type:
        if "Foy" in search_query:
            return HttpResponse("<img src='https://i.imgur.com/tgB48zC.gif'>")

        songs = (
            Song.objects.prefetch_related(
                Prefetch("charts", queryset=charts_qs)
            )
            .select_related("pack")
            .annotate(
                min_meter=Min("charts__meter"),
                max_meter=Max("charts__meter")
            )
            .filter(credit__icontains=search_query))
    elif "pack" in search_type:
        packs = list(Pack.objects.filter(name__icontains=search_query)
                     .annotate(song_count=Count('songs')).order_by("name"))
        packs.sort(key=lambda pack: natural_sort_key(pack.name))
        return render(request, "main.html", {"packs": packs, "search_query": search_query})
    else:
        redirect("/")

    return render(request, "search.html", {"songs": songs, "search_query": search_query})

def pack_view(request, packid):
    """list all the songs in a pack"""
    charts_qs = (
        Chart.objects
        .only("meter", "difficulty", "charttype", "song_id")
        .select_related("song")  # load song to avoid lazy song access per chart
    )
    songs = (
        Song.objects
        .filter(pack_id=packid)
        .select_related("pack")  # fetch pack in same query
        .prefetch_related(
            Prefetch("charts", queryset=charts_qs)
        )
        .annotate(
            min_meter=Min("charts__meter"),
            max_meter=Max("charts__meter")
        )
        .only("id", "title", "subtitle", "artist", "bpms", "credit", "banner", "songlength",
              "titletranslit", "subtitletranslit", "artisttranslit",
              "pack__id", "pack__name")
        .order_by("title")
    )

    # Fetch the pack along with song count in one shot
    parent_pack = (
        Pack.objects
        .filter(id=packid)
        .annotate(song_count=Count("songs"))
        .first()
    )

    charts = (
        Chart.objects
        .filter(song__pack_id=packid)
        .values("meter")
        .annotate(count=Count("id"))
        .order_by("meter")
    )

    chart_info = {'count': 0}
    meter_dist = {}

    if charts:
        for chart in charts:
            meter_dist[chart['meter']] = chart['count']
            chart_info['count'] += chart['count']

        chart_info['min_meter'] = min(meter_dist.keys())
        chart_info['max_meter'] = max(meter_dist.keys())

    # Check if any song in the pack has translations
    translit = any(
        song.titletranslit or song.artisttranslit or song.subtitletranslit
        for song in songs
    )

    context = {
        "pack": parent_pack,
        "songs": songs,
        "charts": charts,
        "meter_dist": meter_dist,
        "chart_info": chart_info,
        "styles": get_all_styles(packid),
        "translit": translit
    }

    return render(request, "pack.html",  context)

def song_list(request, packid):
    """list all the songs in a pack"""
    songs = Song.objects.filter(pack=packid).order_by("title")
    return render(request, "songs.html", {"songs": songs})

def chart_list(request, songid):
    """list all the charts for a song"""
    charts = Chart.objects.filter(song=songid).select_related('chartdata').order_by("meter")
    song = Song.objects.get(id=songid)
    pack = Pack.objects.get(id=song.pack.id)

    translit = any(getattr(song, field) for field in [
        "titletranslit", "artisttranslit", "subtitletranslit"
    ])

    chart_types = {}
    style_types = {}

    for chart in charts:
        ### This is required for the multi level selection
        # Lets us build an organized table of chart types
        game = chart.charttype.split("-")[0]
        style = chart.charttype.split("-")[1]
        if game not in chart_types:
            chart_types[game] = {}
        if style not in chart_types[game]:
            chart_types[game][style] = {}
        chart_types[game][style][chart.id] = chart

        ### this is for single level selection
        if chart.charttype not in style_types:
            style_types[chart.charttype] = {}
        style_types[chart.charttype][chart.id] = chart

        # lets check to see if this chart is in other packs
        common_packs = Pack.objects.filter(songs__charts__chartkey=chart.chartkey).distinct()
        chart.common_packs = common_packs

        # calculate average notes per second
        if chart.npsgraph:
            nps_data = json.loads(chart.npsgraph)
            if len(nps_data) > 0:
                chart.npsavg = sum(nps_data) / len(nps_data)

        # Organize chartData for chartviewer.js
        if hasattr(chart, 'chartdata'):
            # Strip the measure comments some charts have
            chart.chartdata.data = re.sub(r'//.*$', '', chart.chartdata.data, flags=re.MULTILINE)

            blocks = [block.strip() for block in
                      chart.chartdata.data.strip().split(",") if block.strip()]
            notes = []
            for i, block in enumerate(blocks):
                lines = block.splitlines()
                note_block = []
                for line in lines:
                    # Turn "1001" into ["1", "0", "0", "1"]
                    note_block.append(list(line.strip()))
                notes.append([i, note_block])
            column_count = len(notes[0][1][0])
            chart.chartdata.data = notes

            # Notefield width for each chart
            chart.notefield_width = 32 * column_count

    # lets presort the dict and give priority to common game types.
    # Define custom priority
    priority_order = ["dance-single", "dance-double", "dance-solo", "dance-couple",
                      "dance-threepanel",
                      "pump-single", "pump-double", "pump-halfdouble",
                      "smx-single", "smx-double6", "smx-double10",
                      "techno-single9", "techno-double9"]

    def sort_key(charttype):
        try:
            # return (rank, charttype) — charttype used to sort subtypes
            return (priority_order.index(charttype), charttype)
        except ValueError:
            # Unlisted types come after, sorted alphabetically
            return (len(priority_order), charttype)

    # Sort the outer dict
    style_types = OrderedDict(
        sorted(style_types.items(), key=lambda item: sort_key(item[0]))
    )

    def chart_sort_key(chart):
        try:
            return (priority_order.index(chart.charttype), chart.charttype)
        except ValueError:
            return (len(priority_order), chart.charttype)

    charts = sorted(charts, key=chart_sort_key)

    context = {
        "song": song,
        "charts": charts,
        "pack": pack,
        "chart_types": chart_types,
        "style_types": style_types,
        "translit": translit,
    }

    return render(request, "song.html", context)

def main(request):
    """main pack list"""
    packs = list(Pack.objects.annotate(song_count=Count('songs')).order_by("name"))
    packs.sort(key=lambda pack: natural_sort_key(pack.name))

    context = {
        "packs": packs
    }

    return render(request, "main.html", context)

def faq_view(request):
    """faq view"""
    return render(request, "faq.html", {})
#@cache_page(timeout=None)  # Cache the view for 1 day
def list_all_songs(request):
    """list all songs will query all songs and charts"""
    cache_key = "all_songs"

    songs = cache.get(cache_key)

    if not songs:
        # Only fetch needed fields for charts
        charts_qs = Chart.objects.only("meter", "difficulty", "charttype", "song_id")

        # Main query
        songs = (
            Song.objects
            .select_related("pack")  # Pull pack in same query
            .prefetch_related(
                Prefetch("charts", queryset=charts_qs)
            )
            .annotate(
                min_meter=Min("charts__meter"),
                max_meter=Max("charts__meter")
            )
            .only("id", "title", "subtitle", "artist", "credit",
                  "banner", "pack__name", "pack__id", "pack__banner")
            .order_by("title")
        )

        cache.set(cache_key, songs, timeout=60 * 60 * 24)

    context = {
        "songs": songs,
    }

    return render(request, "song_list.html", context)

def get_all_types():
    """get all the types of from Packs"""
    types = Pack.objects.values_list("types", flat=True).distinct()
    out = set()
    for game_type in types:
        for game in game_type:
            out.add(game)
    return out

def get_all_styles(packid):
    """get all the styles from Packs"""
    styles = Pack.objects.filter(id=packid).values_list("style", flat=True).distinct()
    out = set()
    for style in styles:
        for s in style:
            out.add(s)
    return out
