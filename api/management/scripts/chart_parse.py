"""Chart Parse encodes the notedata into songs and chart objects"""
import re
import chardet

class Chart:
    """Chart is the notedata"""
    def __init__(self, charttype, difficulty, meter, credit, lastsecondhint,
                 npspeak, npsgraph, chartkey, taps):
        self.charttype = charttype
        self.difficulty = difficulty
        self.meter = meter
        self.credit = credit
        self.lastsecondhint = lastsecondhint
        self.npspeak = npspeak
        self.npsgraph = npsgraph
        self.chartkey = chartkey
        self.taps = taps

    def __repr__(self):
        return (f"Chart(type={self.charttype}, difficulty={self.difficulty}, meter={self.meter}, "
                f"credit={self.credit}, lastsecondhint={self.lastsecondhint}, "
                f"npspeak={self.npspeak}, chartkey={self.chartkey}, taps={self.taps})")

class Song:
    """Song is the song, contains metadata and charts"""
    def __init__(self, title, artist, subtitle, titletranslit,
                 artisttranslit, subtitletranslit, credit, banner,
                 bpms, filename, musiclength):
        self.title = title
        self.artist = artist
        self.subtitle = subtitle
        self.titletranslit = titletranslit
        self.artisttranslit = artisttranslit
        self.subtitletranslit = subtitletranslit
        self.credit = credit
        self.banner = banner
        self.songlength = musiclength
        self.bpms = bpms
        self.filename = filename
        self.charts = []

    def add_chart(self, chart):
        """Adds a Chart object to the song."""
        self.charts.append(chart)

    def __repr__(self):
        return (f"Song(title={self.title}, artist={self.artist}, credit={self.credit}, "
                f"songlength={self.songlength}, banner={self.banner}, bpms={self.bpms}, "
                f"charts={self.charts})")


def song_to_dict(song):
    """converts Song objects to JSON serializable format"""
    return {
        "title": song.title,
        "artist": song.artist,
        "subtitle": song.subtitle,
        "titletranslit": song.titletranslit,
        "artisttranslit": song.artisttranslit,
        "subtitletranslit": song.subtitletranslit,
        "credit": song.credit,
        "banner": song.banner,
        "songlength": song.songlength,
        "bpms": song.bpms,
        "filename": song.filename,
        "charts": [chart_to_dict(chart) for chart in song.charts]
    }

def chart_to_dict(chart):
    """converts Chart objects to JSON serializable format"""
    return {
        "charttype": chart.charttype,
        "difficulty": chart.difficulty,
        "meter": chart.meter,
        "credit": chart.credit,
        "lastsecondhint": chart.lastsecondhint,
        "npspeak": chart.npspeak,
        "npsgraph": chart.npsgraph,
        "chartkey": chart.chartkey,
        "taps": chart.taps
    }


def parse_radar(values):
    """Parses the radarvalues and pull taps/steps/jumps etc"""
    data = values.split(",")

    if len(values) < 15:
        return None

    # Convert String numbers to ints
    data = list(map(int, map(float, data)))

    radar_keys = [
            "total", "taps", "jumps", "holds", "mines",
            "hands", "rolls", "lifts", "fakes"
    ]

    radar_data = dict(zip(radar_keys, data[5:14]))
    return radar_data

def parse_ssc_data(data):
    """Parses decompressed SSC data into Song and Chart objects."""
    # Convert bytes to string if necessary
    if isinstance(data, bytes):
        result = chardet.detect(data)
        # ugh, annoying
        if result['encoding'] == "Windows-1252":
            result['encoding'] = "utf-8"
        data = data.decode(result['encoding'], errors='replace')

    lines = data.splitlines()

    # Initialize song variables
    song = None
    charts = []

    # Regex patterns for song metadata
    metadata_patterns = {
        "title": re.compile(r"^#TITLE:(.*);"),
        "artist": re.compile(r"^#ARTIST:(.*);"),
        "subtitle": re.compile(r"^#SUBTITLE:(.*);"),
        "titletranslit": re.compile(r"^#TITLETRANSLIT:(.*);"),
        "artisttranslit": re.compile(r"^#ARTISTTRANSLIT:(.*);"),
        "subtitletranslit": re.compile(r"^#SUBTITLETRANSLIT:(.*);"),
        "credit": re.compile(r"^#CREDIT:(.*);"),
        "banner": re.compile(r"^#BANNER:(.*);"),
        "bpms": re.compile(r"^#BPMS:(.*)"),  # Note: no semicolon at the end
        "songlength": re.compile(r"#MUSICLENGTH:(.*);"),
        "filename": re.compile(r"#SONGFILENAME:(.*);")
    }

    # Regex patterns for chart data
    chart_patterns = {
        "charttype": re.compile(r"^#CHARTTYPE:(.*);"),
        "difficulty": re.compile(r"^#DIFFICULTY:(.*);"),
        "meter": re.compile(r"^#METER:(.*);"),
        "credit": re.compile(r"^#CREDIT:(.*);"),
        "lastsecondhint": re.compile(r"^#LASTSECONDHINT:(.*);"),
        "npspeak": re.compile(r"^#NPSPEAK:(.*);"),
        "npsgraph": re.compile(r"^#NPSGRAPH:(.*);"),
        "chartkey": re.compile(r"^#CHARTKEY:(.*);"),
        "taps": re.compile(r"^#RADARVALUES:(.*);")
    }

    current_chart = None
    parsing_chart = False
    parsing_bpms = False
    bpm_data = set()

    # Iterate through each line
    for line in lines:
        line = line.strip()  # Remove extra spaces

        # Parse general song metadata
        if not parsing_chart:
            for key, pattern in metadata_patterns.items():
                match = pattern.match(line)
                if match:
                    value = match.group(1).strip()
                    if key == "bpms":
                        parsing_bpms = True
                        continue
                    if not song:
                        song = Song(title="", artist="", subtitle="", titletranslit="",
                                    artisttranslit="", subtitletranslit="", credit="",
                                    filename="", musiclength=0.0, banner="", bpms="")
                    setattr(song, key, value)

        # Continue parsing BPM data if in progress
        if parsing_bpms:
            if ";" not in line:
                bpm_data.add(int(float(line.split("=")[1])))
                continue
            min_bpm = min(bpm_data)
            max_bpm = max(bpm_data)
            if min_bpm == max_bpm:
                bpms = str(min_bpm)
            else:
                bpms = f"{min_bpm}-{max_bpm}"
            song.bpms = bpms
            parsing_bpms = False
            continue

        # Detect start of a new chart
        if line in ("#NOTEDATA:;", "#NOTES:;"):
            if current_chart:  # Save previous chart
                if "lights" not in current_chart.charttype.lower():
                    charts.append(current_chart)
            parsing_chart = True
            current_chart = Chart(charttype="", difficulty="", meter=0,
                                  credit="", lastsecondhint=0.0, npspeak=0.0,
                                  npsgraph=[], chartkey="", taps="")

        # Parse chart-specific data
        elif parsing_chart:
            for key, pattern in chart_patterns.items():
                match = pattern.match(line)
                if match:
                    value = match.group(1).strip()
                    if key == "meter":
                        value = int(value)  # Convert to integer
                    elif key in ("lastsecondhint", "npspeak", "songlength"):
                        value = float(value)  # Convert to float
                    elif key == "npsgraph":
                        value = [float(x) for x in value.split(",") if x]
                    elif key == "taps":
                        value = parse_radar(value)
                    setattr(current_chart, key, value)

    # Save the last chart
    if current_chart:
        if "lights" not in current_chart.charttype.lower():
            charts.append(current_chart)

    # Attach charts to song
    if song:
        song.charts = charts
        return song

    return None  # Return None if parsing failed
