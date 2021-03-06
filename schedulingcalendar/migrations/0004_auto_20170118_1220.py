# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-18 18:20
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('schedulingcalendar', '0003_auto_20170114_1149'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='departmentmembership',
            name='tier_for_employee',
        ),
        migrations.AddField(
            model_name='departmentmembership',
            name='priority',
            field=models.IntegerField(default=0, verbose_name='Department priority for employee'),
        ),
        migrations.AlterField(
            model_name='schedule',
            name='employee',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='schedulingcalendar.Employee'),
        ),
    ]
