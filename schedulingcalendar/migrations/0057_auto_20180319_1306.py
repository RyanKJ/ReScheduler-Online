# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-03-19 18:06
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('schedulingcalendar', '0056_auto_20180207_1246'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduleSwapApplication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('approved', models.BooleanField(default=None)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='schedulingcalendar.Employee')),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleSwapPetition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(blank=True, default='', max_length=280, verbose_name='Note')),
                ('approved', models.BooleanField(default=None)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='schedulingcalendar.Employee')),
                ('live_schedule', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='schedulingcalendar.LiveSchedule')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='scheduleswapapplication',
            name='schedule_swap_petition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='schedulingcalendar.ScheduleSwapPetition'),
        ),
        migrations.AddField(
            model_name='scheduleswapapplication',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
