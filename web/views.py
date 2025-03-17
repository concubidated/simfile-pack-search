"""web views"""
import re
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.shortcuts import render
from django.db.models import Prefetch, Min, Max, Count, F, Value

from api.models import Pack, Song, Chart

def natural_sort_key(text):
    """order numbers naturally cause we are hoomans"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', text)]

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
    charts = Chart.objects.filter(song__pack=packid).values('meter').annotate(count=Count('id')).order_by('meter')

    meter_dist = {}
    chart_info = {'count': 0}
    for chart in charts:
        meter_dist[chart['meter']] = chart['count']
        chart_info['count'] += chart['count']

    chart_info['min_meter'] = min(meter_dist.keys())
    chart_info['max_meter'] = max(meter_dist.keys())

    print(meter_dist)
    context = {
        "pack": parent_pack,
        "songs": songs,
        "charts": charts,
        "meter_dist": meter_dist,
        "chart_info": chart_info,
    }
    
    return render(request, "pack.html",  context)

def song_list(request, packid):
    """list all the songs in a pack"""
    songs = Song.objects.filter(pack=packid).order_by("title")
    return render(request, "songs.html", {"songs": songs})

def chart_list(request, songid):
    """list all the charts for a song"""
    charts = Chart.objects.filter(song=songid).order_by("meter")
    song = Song.objects.get(id=songid)
    return render(request, "charts.html", {"charts": charts, "song": song})

def main(request):
    """main pack list"""
    packs = list(Pack.objects.annotate(song_count=Count('songs')).order_by("name"))
    packs.sort(key=lambda pack: natural_sort_key(pack.name))
    return render(request, "main.html", {"packs": packs})

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
