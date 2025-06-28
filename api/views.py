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
    packs = list(Pack.objects
                .annotate(song_count=Count('songs')).order_by("name"))
    packs.sort(key=lambda pack: natural_sort_key(pack.name))

    out = "Pack Name, Song Count, Size\n"
    for pack in packs:
        out += f"\"{pack.name}\", {pack.song_count}, {pack.size}"
        out += "\n"
    return HttpResponse(f"<pre>{out}</pre>")

def chart_json(request, chart_id):
    """Chart data used to populate song page"""
    chart = Chart.objects.filter(id=chart_id).select_related('chartdata').first()

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
