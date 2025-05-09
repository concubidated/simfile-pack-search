"""
scan packs will iterated over a list of packs, unzip, 
and parse the songs/charts into the database
"""
import os
import sys
import time
import shutil
import hashlib
import datetime
import subprocess
from pathlib import Path

import chardet
import humanize

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import IntegrityError

from api.models import Pack, Song, Chart, ChartData
from api.management.scripts import sqlite_query, data_import, chart_parse, utils

## Constants
working_path = os.getenv('OUTFOX_WORKING_PATH', './working')
outfox_song_path = os.path.join(working_path, 'Songs')
outfox_cache_path = os.path.join(working_path, 'Cache')
#DOCKER_PATH = "registry.digitalocean.com/outfox-containers/cache-builder"
DOCKER_PATH = "concubidated/outfox-cache:latest"

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
        for file in sorted(os.listdir(packdir)):
            if file.endswith(".zip"):
                packlist.append(os.path.join(packdir, file))

        shutil.rmtree(outfox_song_path, ignore_errors=True)
        os.makedirs(outfox_song_path, exist_ok=True)

        start_index = 0
        for i, pack_path in enumerate(packlist[start_index:], start=start_index):
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
                if db_pack.scanned == 1:
                    #print(f"Skipping {name} already exists")
                    continue

                ## temp method for now
                #if not rescan:
                #    print(f"Skipping {name} already exists")
                #    continue

                # rescan the pack but only delete the song/charts
                Song.objects.filter(pack=db_pack).delete()
                db_pack.style = {}
                db_pack.authors = {}
                db_pack.save()
            except Pack.DoesNotExist:
                pass

            # lets do the thing
            if utils.check_zip(pack_path, outfox_song_path):
                utils.print_warning(f"{i}: {pack_path} skipped, directory path wrong")
                continue

            if not utils.unzip(pack_path, outfox_song_path):
                continue
            if not os.path.exists(fullpath):
                utils.print_warning(f"{i}: {pack_path} skipped, directory path wrong")
                utils.cleanup_dir(outfox_song_path)
                continue
            pack_hash = utils.sha1sum(pack_path)
            size = os.stat(pack_path).st_size
            #date_mtime = datetime.datetime.fromtimestamp(os.stat(pack_path).st_mtime)

            print(name, humanize.naturalsize(size))

            banner = utils.find_image(fullpath)
            new_banner = ""
            if banner:
                # lets store the image in media/images/packs and hash it
                file_ext = os.path.splitext(banner)[1]  # Get the extension (e.g., .txt, .png)
                file_hash = hashlib.sha1(banner.encode()).hexdigest()
                if file_ext in {".avi", ".mp4"}:
                    utils.convert_video_to_gif(banner)
                    file_ext = ".gif"
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

            pack_date = utils.get_newest_zip_file_date(pack_path)
            try:
                pack, _ = Pack.objects.get_or_create(
                    name=name,
                    size=size,
                    date_created=pack_date,
                    sha1sum=pack_hash,
                    scanned=False,
                    extras=found_extra,
                    banner=new_banner,
                    )
            except IntegrityError:
                pack = Pack.objects.get(name=name)


            # delete song.db from cache
            Path(f"{outfox_cache_path}/song.db").unlink(missing_ok=True)

            # run outfox --cache via docker
            try:
                rc = subprocess.run(["docker",
                                        "run",
                                        "--rm",
                                        #"--user", "1000:1000",
                                        "-v", f"{outfox_cache_path}:/outfox/Cache",
                                        "-v", f"{outfox_song_path}:/outfox/Songs",
                                        DOCKER_PATH],
                                        stdout=subprocess.DEVNULL,
                                        #stderr=subprocess.DEVNULL,
                                        check=False
                                    ).returncode
            except subprocess.CalledProcessError as e:
                utils.cleanup_dir(outfox_song_path)
                utils.print_warning(f"Failed to Scan {pack.name}\nError: {e}")
                continue
                #raise SystemExit(f"Error: {e.stderr}") from e

            if rc != 0:
                utils.cleanup_dir(outfox_song_path)
                utils.print_warning(f"Failed to Scan {pack.name}")
                #raise SystemExit("OutFox failed to run - error code:", rc)
                continue

            # now we have a Cache/song.db file we can parse to create the songs and charts
            out = sqlite_query.fetch_song_chart_data(f"{outfox_cache_path}/song.db")

            songs = []
            for song in out:
                data = utils.lz4_decompress(song[0], song[1])
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
                    song_banner = utils.find_image(song_folder)
                    if song_banner:
                        banner_ext = os.path.splitext(song_banner)[1]
                        banner_hash = hashlib.sha1(song_banner.encode()).hexdigest()

                # if an image file was found, lets save it
                if song_banner:
                    if banner_ext.lower() in {".avi", ".mp4"}:
                        utils.convert_video_to_gif(song_banner)
                        banner_ext = ".gif"
                    new_song_banner = f"{banner_hash}{banner_ext}"
                    destination_path = os.path.join('media/images/songs/', new_song_banner)
                    os.makedirs('media/images/songs/', exist_ok=True)
                    shutil.move(song_banner, destination_path)
                    last_song.banner = new_song_banner

            if not songs:
                utils.print_warning(f"{pack.name} ain't got no songs in it")
                continue

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
                        if chart.credit:
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


            # lets actually store all of the notedata for cool stuff like chart previews
            charts = Chart.objects.filter(song__pack=pack)
            for chart in charts:
                try:
                    save_notedata(chart)
                except Exception as e:
                    utils.print_warning(f"Error: save_notedata(): {e}")
                    continue

            pack.types = sorted(list(styletype))
            pack.style = sorted(list(charttype))
            pack.authors = sorted(list(chart_credits))
            pack.scanned = 1
            pack.save()


            # post to discord
            if os.environ.get("DISCORD_WEBHOOK"):
                message = {}
                message["id"] = pack.id
                message["name"] = pack.name
                message["size"] =  humanize.naturalsize(pack.size)
                message["song_count"] = len(songs)
                if pack.banner:
                    message["banner"] = pack.banner
                message["chart_types"] = pack.style
                utils.discord_webhook(message)

            # remove the pack from the working directory before moving on to the next one
            shutil.rmtree(fullpath)

            # move zip file to data folder
            #shutil.move(pack_path, f"/data/packs/{filename}")

        end_time = time.time()  # End timer
        elapsed_time = end_time - start_time
        print(
            f"Scanning complete: {len(packlist)} packs scanned in "
            f"{utils.convert_seconds(elapsed_time)}"
        )
        # after all are complete we can run s3 sync on the packs folder and any changes
        # will be syned, that include new packs and changed packs.

def save_notedata(chart):
    """Parse the chart data from the sm/ssc file and save it to the db"""
    difficulty_map = {
        "basic": "Easy",
        "light": "Easy",
        "another": "Medium",
        "trick": "Medium",
        "standard": "Medium",
        "difficult": "Medium",
        "ssr": "Hard",
        "maniac": "Hard",
        "heavy": "Hard",
        "smaniac": "Challenge",
        "expert": "Challenge",
        "oni": "Challenge",
    }

    is_ssc = False
    chart_filename = chart.song.filename
    meter = chart.meter
    difficulty = chart.difficulty
    charttype = chart.charttype

    if chart_filename.lower().endswith(('.ssc', '.sm')):
        if chart_filename.lower().endswith('.ssc'):
            is_ssc = True
        chart_path = working_path + chart_filename
        if os.path.exists(chart_path):
            lines = read_lines_decoded(chart_path)
            # pull all of the notedata out and store it in the db
            for line in lines:
                chart_found = False
                meta_found = False
                file_charttype = ""
                file_difficulty = ""
                file_description = ""
                file_meter = 0

                if is_ssc:
                    if line.startswith("#NOTEDATA:"):
                        while True:
                            next_line = next(lines, None).strip()
                            if next_line:
                                next_line = next_line.strip()
                            else:
                                continue
                            if next_line.startswith("#STEPSTYPE:"):
                                file_charttype = next_line[len("#STEPSTYPE:"):].strip(';').strip()
                            elif next_line.startswith("#DIFFICULTY:"):
                                file_difficulty = next_line[len("#DIFFICULTY:"):].strip(';').strip()
                            elif next_line.startswith("#METER:"):
                                file_meter = int(
                                    float(next_line[len("#METER:"):].strip(';').strip())
                                    )
                            elif next_line.startswith("#NOTES"): #NOTES or #NOTES2
                                meta_found = True
                                break
                else:
                    if line.strip().startswith("#NOTES:"):
                        # RhythmCodex converts put these on single line :facepalm:
                        if len(line.split(":")) > 6:
                            parts = line.split(":")
                            file_charttype = parts[1]
                            file_description = parts[2]
                            file_difficulty = parts[3]
                            if parts[4]:
                                file_meter = int(float(parts[4]))
                            else:
                                file_meter = 1
                        else:
                            ## ffr r2 pack missing new line...
                            if len(line.split(":")) == 3:
                                file_charttype = line.split(":")[1].strip()
                            else:
                                line = next(lines, None).strip()
                                if line == "":
                                    file_charttype = next(lines, None).split(':')[0].strip()
                                else:
                                    file_charttype = line.split(':')[0].strip()
                            file_description = next(lines, None).split(':')[0].strip()
                            file_difficulty = next(lines, None).split(':')[0].strip()
                            file_meter = int(float(next(lines, None).split(':')[0].strip()))
                        meta_found = True

                if meta_found:
                    # Convert difficulty name using map for old difficulty names
                    diff_name = difficulty_map.get(file_difficulty.lower(), file_difficulty)

                    # Stepmania never had a Challenge back in v1.64-v3.0
                    # so we have to check for a stupid special case where
                    # the chart is hard, but the description is "challenge or smaniac"
                    if diff_name.lower() == 'hard':
                        if "challenge" == file_description.lower() or \
                            "smaniac" == file_description.lower():
                            diff_name = "Challenge"

                    # if all these match, it means this is the correct notedata, let save it
                    if (file_charttype.lower(), file_meter, diff_name.lower()) == \
                        (charttype.lower(), meter, difficulty.lower()):
                        notedata = ""
                        # skip additional metadata if it exists
                        while True:
                            check_line = next(lines, None)
                            if ":" not in check_line and check_line.strip() != \
                                "" and "; " not in check_line:
                                notedata += check_line
                                notedata += '\n'
                                break
                        while True:
                            line = next(lines, None)
                            # Simfile  corrupt, lame.
                            if line is None:
                                utils.print_warning("chart ended early")
                                break
                            notedata += line
                            notedata += '\n'
                            if ';' in line:
                                chart_found = True
                                break
                    else:
                        while True:
                            line = next(lines, None)
                            if line is None:
                                break
                            line.strip()
                            if ';' in line:
                                break
                if chart_found:
                    chart_data = ChartData(chart=chart, data=notedata)
                    chart_data.save()
                    return
            if not chart_found:
                utils.print_warning(
                    f"No Chart found for {chart_path} {charttype} {meter} {difficulty}"
                    )
                return
        else:
            utils.print_warning(f"file missing {chart_path}")
            return
    else:
        return
    utils.print_warning(
        f"Chart was note parsed: {chart_filename} {difficulty} {charttype} {meter}"
        )

def read_lines_decoded(file_path):
    """Returns the lines decoded by the correct charset"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()

    result = chardet.detect(raw_data)
    encoding = result['encoding']

    if encoding == "Windows-1252":
        encoding = "utf-8"
    if encoding == "EUC-TW":
        encoding = "utf-8"

    decoded_data = raw_data.decode(encoding, errors='replace')

    return iter(decoded_data.splitlines())
