# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-05-30 17:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedulingcalendar', '0025_auto_20170530_1148'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessdata',
            name='min_time_for_break',
            field=models.FloatField(default=5, verbose_name='Minimum Schedule Time In Hours For Break Eligability'),
        ),
    ]
