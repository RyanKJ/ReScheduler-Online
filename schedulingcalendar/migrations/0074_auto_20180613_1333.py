# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-13 18:33
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('schedulingcalendar', '0073_businessdata_time_picker_interval'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ManagerProfile',
            new_name='UserProfile',
        ),
    ]
