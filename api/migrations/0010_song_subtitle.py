# Generated by Django 4.2.11 on 2025-03-15 23:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_chart_author_alter_song_credit'),
    ]

    operations = [
        migrations.AddField(
            model_name='song',
            name='subtitle',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
    ]
