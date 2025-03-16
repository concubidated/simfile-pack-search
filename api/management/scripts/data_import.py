"""Data Import script takes song and chart data and imports to the database"""
import json
from api.models import Song, Chart

def save_song_chart_data(pack, data):
    """Stores song and chart data into Django database."""
    saved_songs = 0
    saved_charts = 0

    for parsed in data:
        # dont bother saving the song if there are no charts
        if len(parsed.charts) == 0:
            print(f'{pack.name}: {parsed.title} has no charts, skipping')
            continue
        # Get or create the Song entry
        try:
            song, created = Song.objects.get_or_create(
                pack=pack,
                title=parsed.title[:255],
                artist=parsed.artist[:255],
                subtitle=parsed.subtitle[:255],
                credit=parsed.credit,
                banner=parsed.banner,
                defaults={"songlength": parsed.songlength,
                          "banner": parsed.banner,
                          "bpms": parsed.bpms}
            )
        except Exception as e:
            print("Error: Failed to save song", parsed.title, e)

        if created:
            saved_songs += 1  # Track new songs added

        # Avoid duplicate chart entries
        for chart in parsed.charts:
            if not Chart.objects.filter(chartkey=chart.chartkey).exists():
                Chart.objects.create(
                    song=song,
                    charttype=chart.charttype,
                    difficulty=chart.difficulty,
                    meter=chart.meter,
                    author=chart.credit,
                    lastsecondhint=chart.lastsecondhint,
                    npspeak=chart.npspeak,
                    npsgraph=json.dumps(chart.npsgraph),
                    chartkey=chart.chartkey,
                    taps=chart.taps
                )
                saved_charts += 1

    return saved_songs, saved_charts
