# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-06 20:01
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedulingcalendar', '0046_businessdata_desired_hours_overshoot_alert'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessdata',
            name='hide_end',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='businessdata',
            name='hide_start',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='businessdata',
            name='schedule_end',
            field=models.TimeField(default=datetime.time(17, 0), verbose_name='start time'),
        ),
        migrations.AddField(
            model_name='businessdata',
            name='schedule_start',
            field=models.TimeField(default=datetime.time(8, 0), verbose_name='start time'),
        ),
    ]