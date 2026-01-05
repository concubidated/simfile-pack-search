"""
Helper functions for the scanning packs
"""
import sys
import os
import re
import json
import shutil
import subprocess
import itertools
import hashlib
import zipfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import lz4.block
import requests
import imageio
import imageio.v3 as iio
from PIL import Image

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

def print_warning(string):
    """Add some color to terminal printing"""
    warning = '\033[93m'
    reset = '\033[0m'
    print(f"{warning}{string}{reset}")


def check_zip(zip_path, expected_folder):
    """Check if zip contents are correct before unzipping"""
    if not zipfile.is_zipfile(zip_path):
        return False

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            contents = zip_ref.namelist()

            folder_prefix = expected_folder.rstrip('/') + '/'

            return any(entry.startswith(folder_prefix) for entry in contents)

    except (zipfile.BadZipFile, IOError):
        return False

def unzip(zip_path, extract_to):
    """Unzip using zipfile. If it fails (e.g., path too long), fallback to system unzip."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except (OSError, zipfile.BadZipFile) as e:
        print_warning(f"⚠️ Unzip failed falling back to 7z: {e}")

    try:
        subprocess.run(
            ["unzip", "-f", "-q", zip_path, "-d", extract_to],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Unzipping failed for {zip_path}\nError: {e}")
        return False

def lz4_decompress(blob: bytes, original_size: int) -> bytes:
    """decompress the LZ4 data using block decompression"""
    decompressed_data = lz4.block.decompress(blob, uncompressed_size=original_size)
    return decompressed_data

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
    bn_types = {".png", ".jpeg", ".jpg", ".gif", ".bmp", ".avi", ".mp4"}
    ignore_pattern = re.compile(r"\b(cd|cdtitle|bg|background)\b", re.IGNORECASE)
    prefer_pattern = re.compile(r"\b(bn|banner)\b", re.IGNORECASE)

    best_match = None

    for ext in bn_types:
        files = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith(ext) and os.path.isfile(os.path.join(path, f))
        ]
        valid_files = [f for f in files if not ignore_pattern.search(os.path.basename(f))]

        # Check for a preferred file
        for file in valid_files:
            if prefer_pattern.search(os.path.basename(file)):
                return file

        # If no preferred image, store the first valid one
        if valid_files and best_match is None:
            best_match = valid_files[0]

    return best_match

def convert_video_to_gif(banner_path):
    """Convert a video to a GIF without loading everything into memory."""
    reader = imageio.get_reader(banner_path)  # Stream video instead of loading all frames
    meta = reader.get_meta_data()  # Get video metadata

    colors = 256
    target_fps = 10
    width, _ = meta["size"]

    resize_factor = 1.0
    if width > 512:  # Resize large banners
        resize_factor = 512.0 / width

    original_fps = meta.get("fps", 30)  # Default to 30 FPS if missing
    step = max(1, round(original_fps / target_fps))  # Skip frames to match target FPS

    frames = []

    for i, frame in enumerate(reader):
        if i % step == 0:  # Skip frames to match target FPS
            img = Image.fromarray(frame)

            # Resize while maintaining aspect ratio
            new_size = (int(img.width * resize_factor), int(img.height * resize_factor))
            img = img.resize(new_size, Image.LANCZOS)

            # Convert to GIF palette
            img = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
            frames.append(img)

            # Stop if too many frames (optional safeguard)
            if len(frames) > 100:
                break

    if len(frames) >  1:
        gif_path = f"{banner_path}.gif"
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / target_fps),  # Duration per frame
            loop=0,
            optimize=True
        )

        optimize_gif(gif_path)  # Optimize GIF size
        os.rename(gif_path, banner_path)  # Replace original file with GIF
        #print(f"GIF saved: {banner_path}")
    else:
        print(f"GIF has no frames: {banner_path}")

def optimize_gif(banner_path):
    """Run gifsicle to reduce the size"""
    if not shutil.which("gifsicle"):
        raise EnvironmentError("`gifsicle` is not installed or not found in PATH.")

    try:
        subprocess.run(
            ["gifsicle", "--colors", "256", "-O9", banner_path, "-o", banner_path],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error optimizing {banner_path}: {e}")

def cleanup_dir(directory):
    """Remove all files and folders in a directory"""
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def discord_webhook(pack):
    """sends a post to Discord"""
    if "rescan" in pack:
        url = os.environ.get("DISCORD_RESCAN_WEBHOOK")
    else:
        url = os.environ.get("DISCORD_WEBHOOK")

    chart_type_list = '\n'.join(f"• {ct}" for ct in sorted(pack["chart_types"]))
    name = pack["name"]
    pack_id = pack["id"]
    size = pack["size"]
    song_count = pack["song_count"]
    download_url = f"https://{os.environ.get('DOMAIN')}/pack/{pack_id}"

    embed = {
        "title": "New Pack Added",
        "color": 3447003,
        "fields": [
            {
                "name": f"**{name} - Size {size}**",
                "value": f"Contains {song_count} songs",
            },
            {
                "name": "**Chart Types**",
                "value": chart_type_list or "No charts found",
            },
            {
                "name": "Download",
                "value": f"[Click here to download]({download_url})"
            },
        ],
    }

    if pack.get("banner"):
        embed["image"] = {
            "url": f"https://{os.environ.get('DOMAIN')}/media/images/packs/{pack['banner']}"
        }

    payload = {
        "username": "SMO Pack Scanner",
        "avatar_url": f"http://{os.environ.get('DOMAIN')}/static/images/logo.png",
        "embeds": [embed]
    }

    requests.post(url, json=payload, timeout=10)

def get_newest_zip_file_date(zip_path, n=5):
    """Get the newest date from the files in a zip archive."""
    dates = []

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if '/' not in info.filename:
                continue  # Skip root-level files if needed

            file_date = datetime(*info.date_time)
            dates.append(file_date)

    if not dates:
        return None

    # Sort from newest to oldest
    dates.sort(reverse=True)

    # Return N-th newest if enough, else return the oldest
    return dates[n - 1] if len(dates) >= n else dates[-1]
