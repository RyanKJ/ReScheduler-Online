from django.contrib import admin

from .models import Employee, Department, Schedule, Vacation, RepeatUnavailability, MonthlyRevenue, DepartmentMembership

admin.site.register(Employee)
admin.site.register(Department)
admin.site.register(DepartmentMembership)
admin.site.register(Schedule)
admin.site.register(Vacation)
admin.site.register(RepeatUnavailability)
admin.site.register(MonthlyRevenue)
