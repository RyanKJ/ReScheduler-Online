from django.contrib import admin

from .models import (Employee, Department, Schedule, Vacation,
                     RepeatUnavailability, DesiredTime, MonthlyRevenue,
                     DepartmentMembership, BusinessData, LiveSchedule,
                     LiveCalendar, LiveCalendarVersionTimestamp, DayNoteHeader, 
                     DayNoteBody, ScheduleSwapPetition, UserProfile, VacationApplication)

admin.site.register(Employee)
admin.site.register(Department)
admin.site.register(DepartmentMembership)
admin.site.register(Schedule)
admin.site.register(Vacation)
admin.site.register(RepeatUnavailability)
admin.site.register(DesiredTime)
admin.site.register(MonthlyRevenue)
admin.site.register(BusinessData)
admin.site.register(LiveSchedule)
admin.site.register(LiveCalendar)
admin.site.register(LiveCalendarVersionTimestamp)
admin.site.register(DayNoteHeader)
admin.site.register(DayNoteBody)
admin.site.register(ScheduleSwapPetition)
admin.site.register(UserProfile)
admin.site.register(VacationApplication)

