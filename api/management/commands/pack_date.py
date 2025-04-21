"""test function for parsing song.db"""
import zipfile
import os

from datetime import datetime
from django.core.management.base import BaseCommand

from api.models import Pack, Song, Chart, ChartData

def get_newest_zip_file_date(zip_path):
    """Get the newest date from the files in a zip archive."""
    newest_date = None
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if '/' not in info.filename:
                continue
            file_date = datetime(*info.date_time)
            if not newest_date or file_date > newest_date:
                newest_date = file_date
    return newest_date

class Command(BaseCommand):
    """django admin custom command for pack metadata updates"""
    help = "Update the date pf the packs by using file dates"

    def add_arguments(self, parser):
        parser.add_argument('packdir', type=str, help='Path to pack directory')

    def handle(self, *args, **options):
        self.stdout.write("Updating pack dates... 📅")

        packdir = options['packdir']

        packs = Pack.objects.all()
        for pack in packs:

            pack_path = f"{packdir}/{pack.name}.zip"
            # Skip if the pack is not a zip file

            if not os.path.exists(pack_path):
                self.stdout.write(f"Pack {pack.name} not found at {pack_path}. Skipping...")
                continue

            # Get the newest date from the zip file
            newest_date = get_newest_zip_file_date(pack_path)
            print(f"{pack.name}: {newest_date}")

            # Update the pack's date_created field
            if newest_date:
                pack.date_created = newest_date
                pack.save()

        self.stdout.write("Pack dates updated! ✅")
