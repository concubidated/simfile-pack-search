from django.db import models
from django.utils import timezone


class PackType(models.TextChoices):
    dance = 'dance'
    solo = 'solo'
    pump = 'pump'
    smx = 'smx'
    techno = 'techno'
    mixed = 'mixed'

class PackStyle(models.TextChoices):
    ddr = 'ddr'
    itg = 'itg'
    keyboard = 'keyboard'
    index = 'index'
    spread = 'spread'
    mixed = 'mixed'

class PackSubStyle(models.TextChoices):
    technical = 'technical'
    mods = 'mods'
    stamina = 'stamina'
    dump = 'dump'

class PackSync(models.TextChoices):
    null = '0'
    nine = '9ms'
    other = 'other'
    mixed = 'mixed'

class PackMinVersion(models.TextChoices):
    dwi = 'dwi'
    sm39 = 'Stepmania 3.9'
    oitg = 'OpenITG'
    sm5 = 'Stepmania 5'
    outfox = 'outfox'    

class Pack(models.Model):
    name = models.CharField(max_length=255, unique=True)
    size = models.BigIntegerField()
    scanned = models.BooleanField()
    sha1sum = models.CharField(max_length=40)
    banner = models.CharField(max_length=64, blank=True)
    types = models.JSONField(default=list) 
    style = models.JSONField(default=list)  
    substyle = models.CharField(max_length=32, choices=PackSubStyle.choices, blank=True, null=True)
    sync = models.CharField(max_length=32, choices=PackSync.choices, default=PackSync.null, null=True)
    extras = models.BooleanField()
    min_version = models.CharField(max_length=32, choices=PackMinVersion.choices, default=PackMinVersion.sm39, null=True)
    comments = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=255, blank=True, null=True)
    date_created = models.DateField(blank=True, null=True)
    date_scanned = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} - {self.style}"

class Song(models.Model):
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
        return f"{self.song.title} - {self.difficulty} ({self.meter} - {self.charttype})"

