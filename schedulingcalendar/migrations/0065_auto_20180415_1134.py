# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-04-15 16:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedulingcalendar', '0064_auto_20180410_1457'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='see_all_departments',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='employee',
            name='override_list_view',
            field=models.BooleanField(default=True),
        ),
    ]