# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-11 00:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedulingcalendar', '0072_auto_20180604_1621'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessdata',
            name='time_picker_interval',
            field=models.IntegerField(default=30, verbose_name='time interval'),
        ),
    ]
