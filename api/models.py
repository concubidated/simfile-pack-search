"""Api Models"""
from django.db import models
from django.utils import timezone

class PackStyle(models.TextChoices):
    """PackStyles are the different play styles of the packs"""
    DDR = 'ddr'
    ITG = 'itg'
    KEYBOARD = 'keyboard'
    INDEX = 'index'
    SPREAD = 'spread'
    MIXED = 'mixed'

class PackSubStyle(models.TextChoices):
    """PackSubStyles are the charting types in the pack packs"""
    TECHNICAL = 'technical'
    MODS = 'mods'
    STAMINA = 'stamina'
    DUMP = 'dump'

class PackSync(models.TextChoices):
    """PackSync is the offset of the pack"""
    NULL = '0'
    NINE = '9ms'
    OTHER = 'other'
    MIXED = 'mixed'

class PackMinVersion(models.TextChoices):
    """PackMinVersion is the oldest client that can play the pack"""
    DWI = 'dwi'
    SM39 = 'Stepmania 3.9'
    OITG = 'OpenITG'
    SM5 = 'Stepmania 5'
    OUTFOX = 'outfox'

class Pack(models.Model):
    """Packs are zip files that container the songs"""
    name = models.CharField(max_length=255, unique=True)
    size = models.BigIntegerField()
    scanned = models.BooleanField()
    sha1sum = models.CharField(max_length=40)
    banner = models.CharField(max_length=64, blank=True)
    types = models.JSONField(default=list)
    style = models.JSONField(default=list)
    substyle = models.CharField(max_length=32, choices=PackSubStyle.choices, blank=True, null=True)
    sync = models.CharField(max_length=32,
                            choices=PackSync.choices,
                            default=PackSync.NULL,
                            null=True)
    extras = models.BooleanField()
    min_version = models.CharField(max_length=32,
                                   choices=PackMinVersion.choices,
                                   default=PackMinVersion.SM39,
                                   null=True)
    comments = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=255, blank=True, null=True)
    date_created = models.DateField(blank=True, null=True)
    date_scanned = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} - {self.style}"

class Song(models.Model):
    """Songs are the folders that container the charts"""
    pack = models.ForeignKey(Pack, on_delete=models.CASCADE, related_name="songs") # Link to Packs
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    filename = models.CharField(max_length=100)
    songlength = models.FloatField(default=0)
    banner = models.CharField(max_length=255, blank=True, null=True)
    bpms = models.CharField(max_length=100, blank=True, null=True)  # Can store BPMs as a string
    def __str__(self):
        return f"{self.title} - {self.artist} - {self.pack.name}"

class Chart(models.Model):
    """Charts contain the notedata"""
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="charts")  # Link to Song
    charttype = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=50)
    meter = models.IntegerField()
    lastsecondhint = models.FloatField()
    npspeak = models.FloatField()
    npsgraph = models.JSONField()  # Stores the list of numbers
    chartkey = models.CharField(max_length=64, unique=True)  # Ensure uniqueness
    taps = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.song.__str__()} - {self.difficulty} ({self.meter} - {self.charttype})"
