"""test function for parsing song.db"""
import zipfile
import os

from datetime import datetime
from django.core.management.base import BaseCommand

from api.models import Pack, Song, Chart, ChartData
from api.management.scripts import utils

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
            newest_date = utils.get_newest_zip_file_date(pack_path)
            print(f"{pack.name}: {newest_date}")

            # Update the pack's date_created field
            if newest_date:
                pack.date_created = newest_date
                pack.save()

        self.stdout.write("Pack dates updated! ✅")
