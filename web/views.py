"""web views"""
import re
import os
import json
import string
from collections import OrderedDict
from urllib.parse import quote
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from django.utils.http import content_disposition_header
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.db.models import Prefetch, Min, Max, Count, F, Value, Q
from django.http import JsonResponse
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import escape

from api.models import Pack, Song, Chart, ChartData, PackSubStyle

MIN_SEARCH_QUERY_LEN = 2
SEARCH_MAX_RESULTS = 1000

PACK_LIST_STYLE_FILTERS = {
    "dance-single": "Dance Single",
    "dance-double": "Dance Double",
    "dance-solo": "Dance Solo",
    "pump-single": "Pump Single",
    "pump-double": "Pump Double",
    "smx-single": "SMX Single",
    "smx-double10": "SMX Double 10",
    "techno-single8": "Techno Single 8",
    "techno-single9": "Techno Single 9",
}

_VALID_SUBSTYLES = frozenset(c[0] for c in PackSubStyle.choices)


def _pack_list_page_context():
    """Shared template context for pack list / pack search pages."""
    return {
        "styles": PACK_LIST_STYLE_FILTERS,
        "substyle_choices": PackSubStyle.choices,
    }


def _parse_pack_csv_filter(request, param, valid):
    raw = (request.GET.get(param, "") or "").strip()
    if not raw:
        return []
    return [p for p in (x.strip() for x in raw.split(",")) if p and p in valid]

# DataTables server-side: max rows per request (avoid huge payloads)
PACK_DATATABLES_MAX_LENGTH = 500


def _pack_datatable_cells(pack):
    """Inner HTML for each column (no <td>; DataTables inserts cells)."""
    banner = pack.banner or "nobanner.png"
    img_html = (
        f'<img class="lazy-img img-fluid rounded" style="max-height:50px;" '
        f'data-src="/media/images/packs/{escape(banner)}">'
    )
    name_display = pack.name[:64] + ("..." if len(pack.name) > 64 else "")
    name_html = (
        f'<a class="small text-blue text-decoration-none fw-medium" '
        f'href="/pack/{pack.id}">{escape(name_display)}</a>'
    )
    size_html = (
        f'<span data-sort="{pack.size}" class="small text-center text-gray-300 d-inline-block w-100">'
        f"{filesizeformat(pack.size)}</span>"
    )
    song_count_html = f'<span class="small text-center text-gray-300 d-inline-block w-100">{pack.song_count}</span>'
    type_imgs = []
    for t in pack.types:
        type_imgs.append(
            f'<img alt="{escape(t)}" data-bs-toggle="tooltip" data-bs-placement="top" '
            f'title="{escape(t)} charts" class="img-fluid d-inline-block" '
            f'style="max-width: 30px; filter: invert(0);" '
            f'src="/static/images/types/{escape(t)}.png">'
        )
    types_inner = "".join(type_imgs)
    types_html = (
        f'<span data-sort="{escape(str(pack.types))}" class="small text-center text-gray-300 d-inline-block" '
        f'style="width:100px">{types_inner}</span>'
    )
    if pack.date_created:
        date_str = pack.date_created.strftime("%Y-%m-%d")
    else:
        date_str = pack.date_scanned.strftime("%Y-%m-%d")
    date_html = f'<span class="small text-center text-gray-300 d-inline-block w-100">{escape(date_str)}</span>'
    dl_url = reverse("download_pack", args=[pack.id])
    dl_html = (
        f'<a class="text-center text-gray-300 d-inline-block w-100" href="{escape(dl_url)}">'
        f'<strong class="bi bi-download"></strong></a>'
    )
    return [
        img_html,
        name_html,
        size_html,
        song_count_html,
        types_html,
        date_html,
        dl_html,
    ]


@require_GET
def pack_list_datatables(request):
    """JSON feed for DataTables server-side processing (paginated pack list)."""
    try:
        draw = int(request.GET.get("draw", 0))
    except (TypeError, ValueError):
        draw = 0
    try:
        start = max(0, int(request.GET.get("start", 0)))
    except (TypeError, ValueError):
        start = 0
    try:
        length = int(request.GET.get("length", 25))
    except (TypeError, ValueError):
        length = 25
    if length == -1:
        length = 100
    elif length <= 0:
        length = 25
    elif length > PACK_DATATABLES_MAX_LENGTH:
        length = PACK_DATATABLES_MAX_LENGTH

    search_value = (request.GET.get("search[value]", "") or "").strip()
    pack_name_scope = (request.GET.get("pack_name_scope", "") or "").strip()
    style_filters_raw = request.GET.get("style_filters", "") or ""
    style_filters = [s.strip() for s in style_filters_raw.split(",") if s.strip()]

    substyle_filters = _parse_pack_csv_filter(
        request, "pack_substyle_filters", _VALID_SUBSTYLES
    )

    try:
        order_col = int(request.GET.get("order[0][column]", "1"))
    except (TypeError, ValueError):
        order_col = 1
    order_dir = (request.GET.get("order[0][dir]", "asc") or "asc").lower()
    desc = order_dir == "desc"

    order_map = {
        1: "name",
        2: "size",
        3: "song_count",
        4: "name",
        5: "date_scanned",
    }
    if order_col not in order_map:
        order_col = 1
    order_field = order_map[order_col]
    order_prefix = "-" if desc else ""

    base_qs = (
        Pack.objects.annotate(song_count=Count("songs"))
        .exclude(types=[])
    )
    if pack_name_scope:
        base_qs = base_qs.filter(name__icontains=pack_name_scope)

    records_total = base_qs.count()

    qs = base_qs
    if style_filters:
        style_q = Q()
        for s in style_filters:
            style_q |= Q(style__icontains=f'"{s}"')
        qs = qs.filter(style_q)

    if substyle_filters:
        qs = qs.filter(substyle__in=substyle_filters)

    if search_value:
        qs = qs.filter(
            Q(name__icontains=search_value) | Q(altname__icontains=search_value)
        )

    records_filtered = qs.count()
    qs = qs.order_by(f"{order_prefix}{order_field}", f"{order_prefix}id")
    page = qs[start : start + length]

    return JsonResponse(
        {
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": [_pack_datatable_cells(p) for p in page],
        }
    )


def _song_search_base_queryset():
    """Shared prefetch/annotate for search result rows (keeps columns narrow to reduce memory)."""
    charts_qs = Chart.objects.only("meter", "difficulty", "charttype", "song_id")
    return (
        Song.objects.prefetch_related(Prefetch("charts", queryset=charts_qs))
        .select_related("pack")
        .annotate(
            min_meter=Min("charts__meter"),
            max_meter=Max("charts__meter"),
        )
        .only(
            "id",
            "title",
            "artist",
            "credit",
            "banner",
            "pack__id",
            "pack__name",
            "pack__banner",
        )
        .order_by("title")
    )


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
    uri_name = quote(file_name, safe="")

    Pack.objects.filter(id=pack_id).update(downloads=F('downloads') + 1)
    response = HttpResponse()
    response["X-Accel-Redirect"] = f"/packs/{uri_name}"
    response["Content-Disposition"] = content_disposition_header(True, file_name)
    response["Content-Type"] = "application/zip"
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
        post_type = request.POST.get("type")
        post_search = request.POST.get("search")
        if post_type is not None and post_search is not None:
            q_post = (post_search or "").strip()
            if q_post:
                return redirect(f"/search/{post_type}/{quote(q_post, safe='')}")
            search_type = post_type
            search_query = post_search
        elif request.method == "POST":
            return redirect("/")
        else:
            return redirect("/")

    valid_types = ["title", "artist", "credit", "pack"]
    if search_type not in valid_types:
        return redirect("/")

    q = (search_query or "").strip()
    if len(q) < MIN_SEARCH_QUERY_LEN:
        ctx = {
            "search_query": search_query or "",
            "search_error": (
                f"Please enter at least {MIN_SEARCH_QUERY_LEN} characters "
            ),
        }
        if "pack" in search_type:
            ctx["pack_name_scope"] = ""
            ctx.update(_pack_list_page_context())
            return render(request, "pack_list.html", ctx)
        ctx["songs"] = []
        return render(request, "search.html", ctx)

    if "title" in search_type:
        songs_qs = _song_search_base_queryset().filter(title__icontains=q)
        songs = list(songs_qs[: SEARCH_MAX_RESULTS + 1])
    elif "artist" in search_type:
        songs_qs = _song_search_base_queryset().filter(artist__icontains=q)
        songs = list(songs_qs[: SEARCH_MAX_RESULTS + 1])
    elif "credit" in search_type:
        if "Foy" in q:
            return HttpResponse("<img src='https://i.imgur.com/tgB48zC.gif'>")

        songs_qs = _song_search_base_queryset().filter(credit__icontains=q)
        songs = list(songs_qs[: SEARCH_MAX_RESULTS + 1])
    elif "pack" in search_type:
        ctx = {
            "search_query": q,
            "pack_name_scope": q,
        }
        ctx.update(_pack_list_page_context())
        return render(request, "pack_list.html", ctx)

    search_truncated = len(songs) > SEARCH_MAX_RESULTS
    if search_truncated:
        songs = songs[:SEARCH_MAX_RESULTS]

    return render(
        request,
        "search.html",
        {
            "songs": songs,
            "search_query": q,
            "search_truncated": search_truncated,
            "search_max_results": SEARCH_MAX_RESULTS,
        },
    )

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

    if not parent_pack:
        return redirect("/")

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

    styles = sorted_styles(packid)

    context = {
        "pack": parent_pack,
        "songs": songs,
        "charts": charts,
        "meter_dist": meter_dist,
        "chart_info": chart_info,
        "styles": styles,
        "translit": translit
    }

    return render(request, "pack.html",  context)

def song_list(request, packid):
    """list all the songs in a pack"""
    songs = Song.objects.filter(pack=packid).order_by("title")
    return render(request, "songs.html", {"songs": songs})

def chart_list(request, songid):
    """list all the charts for a song"""
    charts = Chart.objects.filter(song=songid).order_by("meter")
    if not charts:
        return redirect("/")

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

    min_chart_meter = min(charts, key=lambda c: c.meter).meter if charts else 0
    max_chart_meter = max(charts, key=lambda c: c.meter).meter if charts else 0

    context = {
        "song": song,
        "charts": charts,
        "min_chart_meter": min_chart_meter,
        "max_chart_meter": max_chart_meter,
        "pack": pack,
        "chart_types": chart_types,
        "style_types": style_types,
        "translit": translit,
    }

    return render(request, "song.html", context)

def pack_list(request):
    """pack list (rows loaded via DataTables server-side /api/packs/datatables)."""
    ctx = {"pack_name_scope": ""}
    ctx.update(_pack_list_page_context())
    return render(request, "pack_list.html", ctx)

def main(request):
    """main home"""
    packs = list(
        Pack.objects
        .annotate(song_count=Count('songs'))
        .order_by("-date_scanned")[:20]  # descending (most downloaded first)
    )

    context = {
        "packs": packs,
        "disable_filter": True,  # Disable filter for main page
    }

    return render(request, "main.html", context)

def faq_view(request):
    """faq view"""
    return render(request, "faq.html", {})

#@cache_page(timeout=None)  # Cache the view for 1 day
def list_all_songs(request):
    """List all songs and charts efficiently, with cache."""
    cache_key = "all_songs"
    songs = cache.get(cache_key)

    if not songs:
        charts_qs = Chart.objects.only("meter", "difficulty", "charttype", "song_id")

        # Evaluate the QuerySet to list so we store actual results, not lazy queryset
        songs = list(
            Song.objects
            .select_related("pack")
            .prefetch_related(
                Prefetch("charts", queryset=charts_qs)
            )
            .annotate(
                min_meter=Min("charts__meter"),
                max_meter=Max("charts__meter")
            )
            .only(
                "id", "title", "subtitle", "artist", "credit",
                "banner", "pack__id", "pack__name", "pack__banner"
            )
            .order_by("title")
        )

        cache.set(cache_key, songs, timeout=60 * 60 * 24)  # 24 hrs

    return render(request, "song_list.html", {"songs": songs})

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

def sorted_styles(packid):
    """sort styles by priority"""
    # lets presort the dict and give priority to common game types.
    # Define custom priority
    priority_order = ["dance-single", "dance-double", "dance-solo", "dance-couple",
                      "dance-threepanel",
                      "pump-single", "pump-double", "pump-halfdouble",
                      "smx-single", "smx-double6", "smx-double10",
                      "techno-single9", "techno-double9"]

    styles = get_all_styles(packid)
    def sort_key(item):
        try:
            return priority_order.index(item)
        except ValueError:
            return len(priority_order) + 1  # put unknown types at the end

    return sorted(styles, key=sort_key)
