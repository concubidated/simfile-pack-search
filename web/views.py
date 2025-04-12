"""web views"""
import re, json
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.db.models import Prefetch, Min, Max, Count, F, Value

from api.models import Pack, Song, Chart, ChartData

def natural_sort_key(text):
    """order numbers naturally cause we are hoomans"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', text)]

def search(request, search_type=None, search_query=None):
    """search for a song"""
    if not search_type or not search_query:
        search_type = request.POST.get("type")
        search_query = request.POST.get("search")
        return redirect(f"/search/{search_type}/{search_query}")


    valid_types = ["title", "artist", "credit"]
    if search_type not in valid_types:
        return redirect("/")

    charts_qs = Chart.objects.only("meter", "difficulty", "charttype")
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
    else:
        redirect("/")

    return render(request, "search.html", {"songs": songs})

def pack_list(request):
    """list all the packs"""
    packs = list(Pack.objects.all().order_by("name"))
    packs.sort(key=lambda pack: natural_sort_key(pack.name))
    return render(request, "packs.html", {"packs": packs})

def pack(request, packid):
    """list all the songs in a pack"""
    charts_qs = Chart.objects.only("meter", "difficulty", "charttype")

    songs = (
        Song.objects.prefetch_related(
            Prefetch("charts", queryset=charts_qs)
        )
        .filter(pack=packid)
        .select_related("pack")
        .annotate(
            min_meter=Min("charts__meter"),
            max_meter=Max("charts__meter")
        )
        .only("id", "title", "artist", "banner", "pack__name", "pack__id")
        .order_by("title")
        )

    parent_pack = Pack.objects.filter(id=packid).annotate(song_count=Count('songs')).first()
    charts = (
        Chart.objects
        .filter(song__pack=packid)
        .values('meter')
        .annotate(count=Count('id'))
        .order_by('meter')
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

        # Organize chartData for chartviewer.js
        if hasattr(chart, 'chartdata'):
            # Strip the measure comments some charts have
            chart.chartdata.data = re.sub(r'//.*$', '', chart.chartdata.data, flags=re.MULTILINE)

            blocks = [block.strip() for block in chart.chartdata.data.strip().split(",") if block.strip()]
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
            chart.notefield_width = 64 * column_count

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

#@cache_page(60 * 60 * 24)  # Cache the view for 1 day
def list_all_songs(request):
    """list all songs will query all songs and charts"""
    cache_key = "all_songs"

    songs = cache.get(cache_key)

    if not songs:
        # Efficiently load songs with related charts and their meter range
        charts_qs = Chart.objects.only("meter", "difficulty", "charttype")

        songs = (
            Song.objects.prefetch_related(
                Prefetch("charts", queryset=charts_qs)
            )
            .select_related("pack")
            .annotate(
                min_meter=Min("charts__meter"),
                max_meter=Max("charts__meter")
            )
            .only("id", "title", "artist", "banner", "pack__name", "pack__id")
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

def test(request, songid=12669, chartid=43108):
    """test view"""
    if chartid:
        charts = Chart.objects.filter(song=songid).filter(id=chartid).select_related('chartdata')
    else:
        charts = Chart.objects.filter(song=songid).select_related('chartdata').order_by("meter")
    song = Song.objects.get(id=songid)
    pack = Pack.objects.get(id=song.pack.id)


    # Strip the measure comments some charts have
    for chart in charts:
        if chart.chartdata.data:
            chart.chartdata.data = re.sub(r'//.*$', '', chart.chartdata.data, flags=re.MULTILINE)

            blocks = [block.strip() for block in chart.chartdata.data.strip().split(",") if block.strip()]
            notes = []
            for i, block in enumerate(blocks):
                lines = block.splitlines()
                note_block = []
                for line in lines:
                    # Turn "1001" into ["1", "0", "0", "1"]
                    note_block.append(list(line.strip()))
                notes.append([i, note_block])
            chart.chartdata.data = notes
        if chart.charttype == 'dance-double':
            chart.notefield = '512'
        elif chart.charttype == 'dance-single':
            chart.notefield = '256'
        elif chart.charttype == 'dance-solo':
            chart.notefield = '384'
        elif chart.charttype == 'smx-single':
            chart.notefield = '320'
        elif chart.charttype == 'smx-double10' or chart.charttype == 'pump-double':
            chart.notefield = '640'
        else:
            chart.notefield = '300'

    context = {
        "song": song,
        "pack": pack,
        "chart": charts[0],
    }

    return render(request, "test.html", context)
