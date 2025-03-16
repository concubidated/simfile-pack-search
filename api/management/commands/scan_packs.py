"""
scan packs will iterated over a list of packs, unzip, 
and parse the songs/charts into the database
"""
import os
import re
import time
import glob
import shutil
import zipfile
import hashlib
import subprocess
from pathlib import Path

import humanize
import lz4.block
import imageio
from PIL import Image
import numpy as np

from django.core.management.base import BaseCommand
from django.db.models import Count

from api.models import Pack, Song, Chart
from api.management.scripts import sqlite_query, data_import, chart_parse

def convert_seconds(seconds):
    """Converts seconds into human readable format"""
    seconds = round(seconds)  # Round to the nearest second
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")

    return " ".join(parts)

def unzip(file, path):
    """Simple unzip wrapper"""
    with zipfile.ZipFile(file, 'r') as zip_ref:
        zip_ref.extractall(path)

def sha1sum(file):
    """Simple sha1sum wrapper"""
    buf_size = 65536
    sha1 = hashlib.sha1()
    with open(file, 'rb') as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def find_image(path):
    """Scan a folder and returns the first found image"""
    bn_types = {".png", ".jpeg", ".jpg", ".gif", ".bmp"}
    ignore_pattern = re.compile(r"\b(cdtitle|bg|background)\b", re.IGNORECASE)
    prefer_pattern = re.compile(r"\b(bn|banner)\b", re.IGNORECASE)

    best_match = None

    for ext in bn_types:
        files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(ext)]
        valid_files = [f for f in files if not ignore_pattern.search(os.path.basename(f))]

        # Check for a preferred file
        for file in valid_files:
            if prefer_pattern.search(os.path.basename(file)):
                return file

        # If no preferred image, store the first valid one
        if valid_files and best_match is None:
            best_match = valid_files[0]

    return best_match

def lz4_decompress(blob: bytes, original_size: int) -> bytes:
    """Decompress the LZ4 data using block decompression"""
    decompressed_data = lz4.block.decompress(blob, uncompressed_size=original_size)
    return decompressed_data

class Command(BaseCommand):
    """DJango Management Command scan_packs"""
    help = "Imports songs and their related chart data from SQLite into Django"

    def add_arguments(self, parser):
        parser.add_argument('packdir', type=str, help='Path to pack directory')

    def handle(self, *args, **options):
        start_time = time.time()  # Start timer

        self.stdout.write("Parsing new Packs... 📥")
        packdir = options['packdir']

        packlist = []
        # get list of zips in path
        for file in os.listdir(packdir):
            if file.endswith(".zip"):
                packlist.append(os.path.join(packdir, file))

        # debug var for testing, rescans in the future will just be setting
        # the scanned boolean to false in the db
        rescan = True

        # temp path to use for generating the outfox cache
        working_path = os.getenv('OUTFOX_WORKING_PATH', './working')
        outfox_song_path = os.path.join(working_path, 'Songs')
        outfox_cache_path = os.path.join(working_path, 'Cache')

        shutil.rmtree(outfox_song_path, ignore_errors=True)
        os.makedirs(outfox_song_path, exist_ok=True)

        for pack_path in packlist:
            filename = pack_path.split('/')[-1]
            name, extension = os.path.splitext(filename)
            # only support zips, I don't wanna activate winrar
            if extension != ".zip":
                print(f"Skipping {name} {extension} not supported")
                continue
            # we should check if pack already exists in the db
            fullpath = os.path.join(outfox_song_path, name)
            try:
                db_pack = Pack.objects.get(name=name)
                #if db_pack.scanned == 1:
                #    print(f"Skipping {name} already exists")
                #    continue

                ## temp method for now
                if not rescan:
                    print(f"Skipping {name} already exists")
                    continue
                db_pack.delete()
            except Pack.DoesNotExist:
                pass

            # lets do the thing
            unzip(pack_path, outfox_song_path)
            if not os.path.exists(fullpath):
                print(f"{pack_path} skipped, directory path wrong")
                continue
            pack_hash = sha1sum(pack_path)
            size = os.stat(pack_path).st_size

            print(name, humanize.naturalsize(size))

            banner = find_image(fullpath)
            new_banner = ""
            if banner:
                # lets store the image in media/images/packs and hash it
                file_ext = os.path.splitext(banner)[1]  # Get the extension (e.g., .txt, .png)
                file_hash = hashlib.sha1(banner.encode()).hexdigest()
                new_banner = f"{file_hash}{file_ext}"
                destination_path = os.path.join('media/images/packs/', new_banner)
                os.makedirs('media/images/packs/', exist_ok=True)
                shutil.move(banner, destination_path)

            # Is there a folder called 'Additional/Noteskins/Courses ?'
            # lets just have a check for additional content
            extra_dirs = {"appearance", "additional", "additional content", "noteskins", "courses"}
            parent_dir = os.path.dirname(fullpath)
            found_extra = any(
                d.lower() in extra_dirs and os.path.isdir(os.path.join(fullpath, d))
                for d in os.listdir(fullpath))
            if not found_extra:
                found_extra = any(
                    d for d in os.listdir(parent_dir)
                    if d.lower() in extra_dirs and os.path.isdir(os.path.join(parent_dir, d)))

            # At this point we can create the Packs object
            # packname, filesized, scanned, banner, date, scanned,
            # pack.ini will have some of that too
            pack, _ = Pack.objects.get_or_create(
                name=name,
                size=size,
                sha1sum=pack_hash,
                scanned=False,
                extras=found_extra,
                banner=new_banner,
                )

            # next we will run outfox --cache via docker
            docker_path = "registry.digitalocean.com/outfox-containers/cache-builder"

            # delete song.db from cache
            Path(f"{outfox_cache_path}/song.db").unlink(missing_ok=True)

            try:
                rc = subprocess.run(["docker",
                                        "run",
                                        #"--user", "1000:1000",
                                        "-v", f"{outfox_cache_path}:/outfox/Cache",
                                        "-v", f"{outfox_song_path}:/outfox/Songs",
                                        docker_path],
                                        stdout=subprocess.DEVNULL,
                                        #stderr=subprocess.DEVNULL,
                                        check=False
                                    ).returncode
            except subprocess.CalledProcessError as e:
                raise SystemExit(f"Error: {e.stderr}") from e

            if rc != 0:
                raise SystemExit("OutFox failed to run - error code:", rc)

            # now we have a Cache/song.db file we can parse to create the songs and charts
            out = sqlite_query.fetch_song_chart_data(f"{outfox_cache_path}/song.db")

            songs = []
            for song in out:
                data = lz4_decompress(song[0], song[1])
                songs.append(chart_parse.parse_ssc_data(data))

                # lets store the song banner
                last_song = songs[-1]
                song_folder = working_path + os.path.dirname(last_song.filename)
                song_banner = None
                banner_hash = None
                banner_ext = None
                if last_song.banner:
                    song_banner = song_folder + "/" + last_song.banner
                    # does file actually exist?
                    if os.path.exists(song_banner):
                        banner_ext = os.path.splitext(last_song.banner)[1]
                        banner_hash = hashlib.sha1(song_banner.encode()).hexdigest()
                    else:
                        song_banner = None
                        last_song.banner = None
                if not song_banner:
                    song_banner = find_image(song_folder)
                    if song_banner:
                        banner_ext = os.path.splitext(song_banner)[1]
                        banner_hash = hashlib.sha1(song_banner.encode()).hexdigest()

                # if an image file was found, lets save it
                if song_banner:
                    if "avi" in banner_ext:
                        reader = imageio.get_reader(song_banner)
                        fps = reader.get_meta_data()['fps']
                        width, height = reader.get_meta_data()['size']

                        resize_factor = 1.0

                        if width > 418: #standard banner size wtf lol
                            resize_factor = 418.0/width

                        with imageio.get_writer(
                                f"{song_banner}.gif", mode='I', loop=0, fps=fps) as writer:
                            for frame in reader:
                                if resize_factor:
                                    pil_frame = Image.fromarray(frame)
                                    pil_frame = pil_frame.resize(
                                            (int(resize_factor*width), int(resize_factor*height)))
                                    resized_frame = np.array(pil_frame)
                                    writer.append_data(resized_frame)
                                else:
                                    writer.append_data(frame)
                        os.rename(f"{song_banner}.gif", song_banner)
                        banner_ext = ".gif"
                    new_song_banner = f"{banner_hash}{banner_ext}"
                    destination_path = os.path.join('media/images/songs/', new_song_banner)
                    os.makedirs('media/images/songs/', exist_ok=True)
                    shutil.move(song_banner, destination_path)
                    last_song.banner = new_song_banner

            # lets build a list of chart authors for the pack metadata

            # songs might have multiple chart authors, so if the song does
            # not have a credit defined, lets check the chart data itself
            # lets build a list of chart authors and save that to the song
            # even though in most cases this will be a single author
            chart_credits = set()
            for song in songs:
                song_credits = set()
                if song.credit:
                    chart_credits.add(song.credit)
                    song_credits.add(song.credit)
                    song.credit = list(song_credits)
                else:
                    for chart in song.charts:
                        chart_credits.add(chart.credit)
                        song_credits.add(chart.credit)
                    song.credit = list(song_credits)

            data_import.save_song_chart_data(pack, songs)

            charts_grouped = (
                Chart.objects.filter(song__pack=pack)
                .values("charttype")  # Group by charttype
                .annotate(count=Count("id"))  # Count charts in each group
            )

            # save them in the pack table, might make future queries much simpler.
            charttype = set()
            styletype = set()
            for chart in charts_grouped:
                charttype.add(chart['charttype'])
                styletype.add(chart['charttype'].split('-')[0])


            pack.types = list(styletype)
            pack.style = list(charttype)
            pack.authors = list(chart_credits)
            pack.scanned = 1
            pack.save()

            # remove the pack from the working directory before moving on to the next one
            shutil.rmtree(fullpath)

            # move zip file to data folder
            shutil.move(pack_path, f"/data/packs/{filename}")

        end_time = time.time()  # End timer
        elapsed_time = end_time - start_time
        print(
            f"Scanning complete: {len(packlist)} packs scanned in {convert_seconds(elapsed_time)}")

        # think about if we wanna store the entire notedata as well
        # it could have a constraint to the charts table and just have the raw data
        # we could then have a chart visualizer on the site too

        # after all are complete we can run s3 sync on the packs folder and any changes
        # will be syned, that include new packs and changed packs.
