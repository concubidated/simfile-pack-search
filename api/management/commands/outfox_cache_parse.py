"""test function for parsing song.db"""
from django.core.management.base import BaseCommand
import lz4.block
from api.management.scripts import sqlite_query, data_import, chart_parse


def lz4_decompress(blob: bytes, original_size: int) -> bytes:
    """decompress the LZ4 data using block decompression"""
    decompressed_data = lz4.block.decompress(blob, uncompressed_size=original_size)
    return decompressed_data

class Command(BaseCommand):
    """django admin custom command for parsing song.db"""
    help = "Imports songs and their related chart data from SQLite into Django"

    def add_arguments(self, parser):
        parser.add_argument('songdb', type=str, help='Path to song.db')

    def handle(self, *args, **options):
        self.stdout.write("Fetching songs and charts from SQLite... 📥")
        songdb = options['songdb']
        out = sqlite_query.fetch_song_chart_data(songdb)

        parsed = []
        for song in out:
            data = lz4_decompress(song[0], song[1])
            parsed.append(chart_parse.parse_ssc_data(data))

        saved_songs, saved_charts = data_import.save_song_chart_data("Test Pack", parsed)

        self.stdout.write(
            f"Import complete! ✅ {saved_songs} new songs, {saved_charts} new charts saved.")
