"""web views"""
from django.shortcuts import render
from api.models import Pack, Song, Chart

def pack_list(request):
    """list all the packs"""
    packs = Pack.objects.all().order_by("name")
    return render(request, "packs.html", {"packs": packs})

def song_list(request, packid):
    """list all the songs in a pack"""
    songs = Song.objects.filter(pack=packid).order_by("title")
    return render(request, "songs.html", {"songs": songs})

def chart_list(request, songid):
    """list all the charts in a song"""
    charts = Chart.objects.filter(song=songid).order_by("meter")
    song = Song.objects.get(id=songid)
    return render(request, "charts.html", {"charts": charts, "song": song})
