"""Api view"""

import re
import json
from django.http import JsonResponse, HttpResponse
from django.db.models import Prefetch, Min, Max, Count, F, Value

from api.models import Pack, Song, Chart, ChartData


def natural_sort_key(text):
    """order numbers naturally cause we are hoomans"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', text)]

def pack_list(request):
    """api call to list packs"""
    packs = list(
        Pack.objects.annotate(song_count=Count("songs")).order_by("name")
    )
    packs.sort(key=lambda pack: natural_sort_key(pack.name))

    out = "ID, Pack Name, Song Count, Size, Sync, PackType, Substyle, Min Version\n"
    for p in packs:
        cols = (
            p.id,
            f'"{p.name}"',
            p.song_count,
            p.size,
            p.sync,
            p.packType,
            p.substyle,
            p.min_version,
        )
        out += ", ".join(map(str, cols)) + "\n"

    return HttpResponse(out, content_type="text/plain")

def chart_json(request, chart_id):
    """Chart data used to populate song page"""
    chart = Chart.objects.filter(id=chart_id).select_related('chartdata').first()

    chart.npsgraph = chart.npsgraph.replace("NaN", "0.0")
    nps_data = json.loads(chart.npsgraph)

    if len(nps_data) > 0:
        chart.npsavg = sum(nps_data) / len(nps_data)

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

        if "Copied from" in chart.author:
            chart.author = None

        # Notefield width for each chart
        chart.notefield_width = 32 * column_count

        # lets check to see if this chart is in other packs
        common_packs = Pack.objects.filter(songs__charts__chartkey=chart.chartkey).distinct()
        chart.common_packs = common_packs

    return JsonResponse({
        "chart_id": chart.id,
        "author": chart.author,
        "npsgraph": chart.npsgraph,
        "npsavg": chart.npsavg if hasattr(chart, 'npsavg') else 0,
        "npspeak": chart.npspeak,
        "meter": chart.meter,
        "charttype": chart.charttype,
        "difficulty": chart.difficulty,
        "taps": chart.taps,
        "chart_key": chart.chartkey,
        "song": {
            "id": chart.song.id,
            "name": chart.song.title,
            "artist": chart.song.artist,
            "bpm": chart.song.bpms,
            "length": chart.song.songlength,
        },
        "chartdata": chart.chartdata.data if hasattr(chart, 'chartdata') else None,
        "chartwidth": chart.notefield_width if hasattr(chart, 'notefield_width') else 0,
        "common_packs": [
            {
                "id": pack.id,
                "name": pack.name,
                "size": pack.size
            } for pack in chart.common_packs
        ] if hasattr(chart, 'common_packs') else []
    })

def chart_json_by_key(request, chart_key):
    """Chart data used to populate song page by chart key"""
    chart = Chart.objects.filter(chartkey=chart_key).first()

    if not chart:
        return JsonResponse({"error": "Chart not found"}, status=404)

    return chart_json(request, chart.id)

def _request_wants_exact(request):
    v = (request.GET.get("exact") or "").strip().lower()
    return v in ("1", "true", "on", "yes")


def _matching_song_titles(pack, query_type, q, exact):
    """Titles of songs in this pack that satisfy the search (empty for type=pack)."""
    if query_type == "pack":
        return []
    songs = pack.songs.all()
    if query_type == "title":
        qs = songs.filter(title__iexact=q) if exact else songs.filter(title__icontains=q)
    elif query_type == "artist":
        qs = songs.filter(artist__iexact=q) if exact else songs.filter(artist__icontains=q)
    elif query_type == "credit":
        if exact:
            titles = []
            for song in songs.iterator():
                if any(
                    str(c).strip().lower() == q.lower()
                    for c in (song.credit or [])
                ):
                    titles.append(song.title)
            return sorted(set(titles), key=natural_sort_key)
        qs = songs.filter(credit__icontains=q)
    else:
        return []
    titles = list(qs.values_list("title", flat=True))
    return sorted(set(titles), key=natural_sort_key)


def search(request):
    """Search for packs"""
    search_query = request.GET.get("query")
    query_type = request.GET.get("type")
    exact = _request_wants_exact(request)
    q = (search_query or "").strip()

    if not q or query_type not in ("title", "artist", "credit", "pack"):
        return JsonResponse({"results": []})

    packs = Pack.objects.none()
    if query_type == "title":
        flt = {"songs__title__iexact": q} if exact else {"songs__title__icontains": q}
        packs = Pack.objects.filter(**flt).distinct().order_by("name")
    elif query_type == "artist":
        flt = {"songs__artist__iexact": q} if exact else {"songs__artist__icontains": q}
        packs = Pack.objects.filter(**flt).distinct().order_by("name")
    elif query_type == "credit":
        if exact:
            pack_ids = set()
            candidates = Song.objects.filter(credit__icontains=q).only(
                "pack_id", "credit"
            )
            for song in candidates.iterator(chunk_size=500):
                if any(
                    str(c).strip().lower() == q.lower()
                    for c in (song.credit or [])
                ):
                    pack_ids.add(song.pack_id)
            packs = Pack.objects.filter(id__in=pack_ids).order_by("name")
        else:
            packs = (
                Pack.objects.filter(songs__credit__icontains=q)
                .distinct()
                .order_by("name")
            )
    elif query_type == "pack":
        flt = {"name__iexact": q} if exact else {"name__icontains": q}
        packs = Pack.objects.filter(**flt).order_by("name")

    packs_list = []
    for pack in packs:
        packs_list.append({
            "id": pack.id,
            "name": pack.name,
            "songs_count": pack.songs.count(),
            "type": pack.types,
            "matching_songs": _matching_song_titles(pack, query_type, q, exact),
        })
    return JsonResponse({"results": packs_list})
