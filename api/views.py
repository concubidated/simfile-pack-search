"""Api view"""

import re
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
        out += f"{pack.name}, {pack.song_count}, {pack.size}"
        out += "\n"
    return HttpResponse(f"<pre>{out}</pre>")
