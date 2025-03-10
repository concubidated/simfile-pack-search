"""Chart Parse encodes the notedata into songs and chart objects"""
import re

class Chart:
    """Chart is the notedata"""
    def __init__(self, charttype, difficulty, meter, lastsecondhint,
                 npspeak, npsgraph, chartkey, taps):
        self.charttype = charttype
        self.difficulty = difficulty
        self.meter = meter
        self.lastsecondhint = lastsecondhint
        self.npspeak = npspeak
        self.npsgraph = npsgraph
        self.chartkey = chartkey
        self.taps = taps

    def __repr__(self):
        return (f"Chart(type={self.charttype}, difficulty={self.difficulty}, meter={self.meter}, "
                f"lastsecondhint={self.lastsecondhint}, npspeak={self.npspeak}, "
                f"chartkey={self.chartkey}, taps={self.taps})")


class Song:
    """Song is the song, contains metadata and charts"""
    def __init__(self, title, artist, banner, bpms, filename, musiclength):
        self.title = title
        self.artist = artist
        self.banner = banner
        self.songlength = musiclength
        self.bpms = bpms
        self.filename = filename
        self.charts = []

    def add_chart(self, chart):
        """Adds a Chart object to the song."""
        self.charts.append(chart)

    def __repr__(self):
        return (f"Song(title={self.title}, artist={self.artist}, songlength={self.songlength}, "
                f"banner={self.banner}, bpms={self.bpms}, charts={self.charts})")


def song_to_dict(song):
    """converts Song objects to JSON serializable format"""
    return {
        "title": song.title,
        "artist": song.artist,
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
        "lastsecondhint": chart.lastsecondhint,
        "npspeak": chart.npspeak,
        "npsgraph": chart.npsgraph,
        "chartkey": chart.chartkey,
        "taps": chart.taps
    }

def parse_taps(taps):
    """Parases the taps string from the notedata."""
    data = taps.replace("#TAPS:", "").strip(";")
    items = data.split(",")
    parsed_data = {items[i]: int(items[i + 1]) for i in range(0, len(items), 2)}
    return parsed_data

def parse_ssc_data(data):
    """Parses decompressed SSC data into Song and Chart objects."""
    # Convert bytes to string if necessary
    if isinstance(data, bytes):
        data = data.decode('utf-8')

    # Split data into lines
    lines = data.splitlines()

    # Initialize song variables
    song = None
    charts = []

    # Regex patterns for song metadata
    metadata_patterns = {
        "title": re.compile(r"^#TITLE:(.*);"),
        "artist": re.compile(r"^#ARTIST:(.*);"),
        "banner": re.compile(r"^#BANNER:(.*);"),
        "bpms": re.compile(r"^#BPMS:(.*)\n"),
        "songlength": re.compile(r"#MUSICLENGTH:(.*);"),
        "filename": re.compile(r"#SONGFILENAME:(.*);")
    }

    # Regex patterns for chart data
    chart_patterns = {
        "charttype": re.compile(r"^#CHARTTYPE:(.*);"),
        "difficulty": re.compile(r"^#DIFFICULTY:(.*);"),
        "meter": re.compile(r"^#METER:(.*);"),
        "lastsecondhint": re.compile(r"^#LASTSECONDHINT:(.*);"),
        "npspeak": re.compile(r"^#NPSPEAK:(.*);"),
        "npsgraph": re.compile(r"^#NPSGRAPH:(.*);"),
        "chartkey": re.compile(r"^#CHARTKEY:(.*);"),
        "taps": re.compile(r"^#TAPS:(.*);")
    }

    current_chart = None
    parsing_chart = False

    # Iterate through each line
    for line in lines:
        line = line.strip()  # Remove extra spaces

        # Parse general song metadata
        if not parsing_chart:
            for key, pattern in metadata_patterns.items():
                match = pattern.match(line)
                if match:
                    value = match.group(1).strip()
                    if not song:
                        song = Song(title="", artist="", filename="",
                                    musiclength=0.0, banner="", bpms="")
                    setattr(song, key, value)

        # Detect start of a new chart
        if line in ("#NOTEDATA:;", "#NOTES:;"):
            if current_chart:  # Save previous chart
                charts.append(current_chart)
            parsing_chart = True
            current_chart = Chart(charttype="", difficulty="", meter=0, lastsecondhint=0.0,
                                  npspeak=0.0, npsgraph=[], chartkey="", taps="")

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
                        value = parse_taps(value)
                    setattr(current_chart, key, value)

    # Save the last chart
    if current_chart:
        # lets not save light charts lol
        if 'lights' not in current_chart.charttype:
            charts.append(current_chart)

    # Attach charts to song
    if song:
        song.charts = charts
        return song

    return None  # Return None if parsing failed
