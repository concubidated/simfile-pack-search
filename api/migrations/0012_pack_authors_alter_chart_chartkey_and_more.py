# Generated by Django 4.2.11 on 2025-03-17 02:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_pack_authors_alter_chart_npsgraph_alter_chart_taps_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chart',
            name='chartkey',
            field=models.CharField(max_length=64),
        ),
        migrations.AlterUniqueTogether(
            name='chart',
            unique_together={('chartkey', 'song')},
        ),
    ]
