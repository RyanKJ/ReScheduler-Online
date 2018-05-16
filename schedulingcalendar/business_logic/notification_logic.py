import json
import bisect
import calendar
from datetime import date, datetime, timedelta, time
from operator import itemgetter
from django.utils import timezone
from django.contrib.auth.models import User
from ..models import (Schedule, Department, DepartmentMembership, MonthlyRevenue,
                     Employee, Vacation, RepeatUnavailability, BusinessData,
                     Absence, DesiredTime, LiveSchedule, LiveCalendar,
                     LiveCalendarDepartmentViewRights, LiveCalendarEmployeeViewRights)
from twilio.rest import Client


def set_view_rights(user, live_calendar, department_view, employee_view):
    """Create/edit view rights for departments/employees for live calendar."""
    
    # Delete old view rights for this live calendar
    oldDepartmentViewRights = LiveCalendarDepartmentViewRights.objects.filter(user=user, live_calendar=live_calendar).delete()
    oldEmployeeViewRights = LiveCalendarEmployeeViewRights.objects.filter(user=user, live_calendar=live_calendar).delete()
    
    # Create new view rights for this live calendar
    departments = Department.objects.filter(user=user, id__in=department_view)
    employees = Employee.objects.filter(user=user, id__in=employee_view)
    
    newDepartmentViewRights = []
    newEmployeeViewRights = []
    
    for department in departments:
        depViewRight = LiveCalendarDepartmentViewRights(user=user,
                                                        live_calendar=live_calendar,
                                                        department_view_rights=department)  
        newDepartmentViewRights.append(depViewRight)
    for employee in employees:
        empViewRight = LiveCalendarEmployeeViewRights(user=user,
                                                      live_calendar=live_calendar,
                                                      employee_view_rights=employee)
        newEmployeeViewRights.append(empViewRight)
        
    LiveCalendarDepartmentViewRights.objects.bulk_create(newDepartmentViewRights)
    LiveCalendarEmployeeViewRights.objects.bulk_create(newEmployeeViewRights)                                                   
    
    
def send_employee_texts(user, department, date, business_data, live_calendar, view_rights, notify_all):
    """Send texts to employees who have new or edited schedules."""
    account_sid = ''
    auth_token = ''
    client = Client(account_sid, auth_token)
    
    # Get employees who have new/edited schedules who have a phone # and right to view
    # Then send them an appropriately templated SMS message.
    end_body = business_data.company_name + ". Check your schedules at: https://schedulehours.com/live_calendar"
    employees_and_changes = get_employees_to_notify(user, live_calendar, view_rights, notify_all)
    for emp_sch_change in employees_and_changes:
        employee = emp_sch_change[0]
        if employee.phone_number:
            type = emp_sch_change[1]['change_type']
            if type == 'new' and live_calendar.version == 1:
                start_body = "You have new schedules for department " + department.name + " in " + date.strftime("%B") + " at " 
            elif type == 'new' and notify_all:
                start_body = "A new version of the calendar has been published for department " + department.name + " in " + date.strftime("%B") + " at " 
            elif type == 'multiple':
                start_body = "You have multiple schedule changes for department " + department.name + " in " + date.strftime("%B") + " at " 
            elif type == 'delete':
                sch_date = emp_sch_change[1]['live_sch'].start_datetime.strftime("%A, %B %d")
                start_body = "Your schedule on " + sch_date + " has been removed"
                start_body += " in department " + department.name + " at "  
            elif type == 'time_edit':
                sch_date = emp_sch_change[1]['live_sch'].start_datetime.strftime("%A, %B %d")
                start_body = "Your schedule on " + sch_date +  " had its time changed" 
                start_body += " in department " + department.name + " at " 
            elif type == 'note_edit':
                sch_date = emp_sch_change[1]['live_sch'].start_datetime.strftime("%A, %B %d")
                start_body = "Your schedule on " + sch_date +  " had its note changed" 
                start_body += " in department " + department.name + " at "  
            elif type == 'add':
                sch_date = emp_sch_change[1]['live_sch'].start_datetime.strftime("%A, %B %d")
                start_body = "You have been added to a schedule on the date " + sch_date
                start_body += " in department " + department.name + " at "  
                
            message = client.messages.create(body=start_body + end_body,
                                             from_="+16123244570",
                                             to="+1" + employee.phone_number)
    

def get_employees_to_notify(user, live_calendar, view_rights, notify_all):
    """Get list of employees who have new or edited schedules to send SMS text."""
    employees_and_changes = []
    
    live_schedules = (LiveSchedule.objects.select_related('employee')
                                          .filter(user=user,
                                                  calendar=live_calendar,
                                                  version=live_calendar.version))
                                            
    if live_calendar.version == 1 or notify_all:
        for live_sch in live_schedules:
            employee = live_sch.employee
            if not any(emp[0] == employee for emp in employees_and_changes):
                if _has_right_to_view(employee, view_rights, live_calendar, user):
                    employees_and_changes.append((employee, {'change_type': 'new'}))
    else:
        old_live_schedules = (LiveSchedule.objects.select_related('employee')
                                                  .filter(user=user,
                                                          calendar=live_calendar,
                                                          version=live_calendar.version - 1))      
        for old_live_sch in old_live_schedules:
            employee = old_live_sch.employee
            # Case where old schedule was deleted
            if old_live_sch.schedule == None:
                if _has_right_to_view(employee, view_rights, live_calendar, user):
                    emp_in_list = None
                    for emp_change in employees_and_changes:
                        if emp_change[0] == employee:
                            emp_in_list = True
                            emp_change[1] = {'change_type': 'multiple'}
                            break
                    if not emp_in_list:
                        employees_and_changes.append([employee, {'change_type': 'delete', 'live_sch': old_live_sch}])
                            
            # Check for case where old schedule was changed
            for new_live_sch in live_schedules:
                if old_live_sch.schedule == new_live_sch.schedule:
                    has_schedule_changed, info = _has_schedule_changed(old_live_sch, new_live_sch)
                    if has_schedule_changed:
                        # Case where schedule had employee change requires notifying 2 different employees
                        if info['change_type'] == 'employee_edit':
                            new_employee = info['new_live_sch'].employee
                            
                            # Check if new employee is already in notification list
                            new_emp_in_list = None
                            for emp_change in employees_and_changes:
                                if emp_change[0] == new_employee:
                                    new_emp_in_list = True
                                    emp_change[1] = {'change_type': 'multiple'}
                                    break
                            if not new_emp_in_list:
                                employees_and_changes.append([employee, {'change_type': 'add', 'live_sch': info['new_live_sch']}])     
                              
                            # Check if old employee is already in notification list
                            emp_in_list = None
                            for emp_change in employees_and_changes:
                                if emp_change[0] == employee:
                                    emp_in_list = True
                                    emp_change[1] = {'change_type': 'multiple'}
                                    break
                            if not emp_in_list:
                                employees_and_changes.append([employee, {'change_type': 'delete', 'live_sch': info['old_live_sch']}])     
                      
                        # Case where time or note was edited
                        else:
                          emp_in_list = None
                          for emp_change in employees_and_changes:
                              if emp_change[0] == employee:
                                  emp_in_list = True
                                  emp_change[1] = {'change_type': 'multiple'}
                                  break
                          if not emp_in_list:
                              employees_and_changes.append([employee, info])     
                    break
        
        # Check for newly added schedules
        for live_sch in live_schedules:
            employee = live_sch.employee
            if not any(live_sch.schedule == old_live_sch.schedule for old_live_sch in old_live_schedules):
                emp_in_list = None
                for emp_change in employees_and_changes:
                    if emp_change[0] == employee:
                        emp_in_list = True
                        emp_change[1] = {'change_type': 'multiple'}
                        break
                if not emp_in_list:
                    employees_and_changes.append([employee, {'change_type': 'add', 'live_sch': live_sch}])
                                        
    return employees_and_changes
 

def _has_right_to_view(employee, view_rights, live_calendar, user):
    """Return boolean that says if the employee can view the given live calendar."""
    if view_rights['all_employee_view']:
        return True
        
    # Check if employee belongs to a department that has right to view live calendar
    departments_of_employee = (DepartmentMembership.objects.select_related('department')
                                                           .filter(user=user, employee=employee))
    for dep_view_right in view_rights['department_view']:
        for dep_mem_of_employee in departments_of_employee:
            if dep_view_right == departments_of_employee.department.id:
                  return True      
                  
    # Check if employee has explicit view rights
    for emp_view_right in view_rights['employee_view']:
        if emp_view_right == employee.id:
            return True
    
    return False
    
    
def _has_schedule_changed(old_live_sch, new_live_sch):
    """Compare 2 live schedules from different version to check if they have changed."""
    has_changed = False
    info = {}
    
    if old_live_sch.employee != new_live_sch.employee:
        has_changed = True
        info = {'change_type': 'employee_edit', 'old_live_sch': old_live_sch, 'new_live_sch': new_live_sch}
    elif (old_live_sch.start_datetime != new_live_sch.start_datetime or
          old_live_sch.end_datetime != new_live_sch.end_datetime or
          old_live_sch.hide_start_time != new_live_sch.hide_start_time or
          old_live_sch.hide_end_time != new_live_sch.hide_end_time):
        has_changed = True
        info = {'change_type': 'time_edit', 'live_sch': new_live_sch}
    elif old_live_sch.schedule_note != new_live_sch.schedule_note:
        has_changed = True
        info = {'change_type': 'note_edit', 'live_sch': new_live_sch}
    
    return has_changed, info
    
    
def view_right_send_employee_texts(user, department, date, business_data, live_calendar, new_view_rights):  
    """Send texts to employees who did not previously have right to view schedules."""
    
    if live_calendar.all_employee_view: # Every employee could already see schedules
        return
    
    # Get old view rights
    old_view_rights = {'department_view': [], 'employee_view': []}        
    department_view_rights = LiveCalendarDepartmentViewRights.objects.filter(user=user, live_calendar=live_calendar)
    employee_view_rights = LiveCalendarEmployeeViewRights.objects.filter(user=user, live_calendar=live_calendar)      
    for dep_view_right in department_view_rights:
        old_view_rights['department_view'].append(dep_view_right.department_view_rights.id)
    for emp_view_right in employee_view_rights:
        old_view_rights['employee_view'].append(emp_view_right.employee_view_rights.id)
    
    # Get list of employees to notify
    employees = view_right_get_employees_to_notify(user, old_view_rights, new_view_rights)
    
    # Notify employees
    account_sid = ''
    auth_token = ''
    client = Client(account_sid, auth_token)
    body = "New schedules have been posted for department " + department.name + " in " + date.strftime("%B") + " at " 
    body += business_data.company_name + ". Check your schedules at: https://schedulehours.com/live_calendar"
    for employee in employees:
        if employee.phone_number:
            message = client.messages.create(body=body,
                                             from_="+16123244570",
                                             to="+1" + employee.phone_number)
        
    
def view_right_get_employees_to_notify(user, old_view_rights, new_view_rights):
    """Get list of employees who did not have right to view schedules, but now do."""
    employees = []
    original_new_dep = []
    original_new_emp = []
    dep_with_prev_view_rights = []
    emp_with_prev_view_rights = []
    
    # Sort departments and employees by whether they already had right to view or not 
    for dep in new_view_rights['department_view']:
        if dep in old_view_rights['department_view']:
            dep_with_prev_view_rights.append(dep)
        else:
            original_new_dep.append(dep)   
    for employee in new_view_rights['employee_view']:
        if employee in old_view_rights['employee_view']:
            emp_with_prev_view_rights.append(employee)
        else:
            original_new_emp.append(employee)

    # Get employees that belong to each department that can now view it
    dep_memberships = (DepartmentMembership.objects.select_related('employee')
                                                   .filter(user=user, department__in=original_new_dep))
    employees.extend(dep_mem.employee for dep_mem in dep_memberships)
    
    # Get employees who can explicitly view it, only add if they aren't already in list
    explicit_employees = Employee.objects.filter(user=user, id__in=original_new_emp)
    for employee in explicit_employees:
        if not employee in employees:
            employees.append(employee)
    
    # Subtract employees who could already see schedules due to membership in another department
    # that had previous view right
    dep_memberships_with_prev_view_rights = (DepartmentMembership.objects.select_related('employee')
                                                                 .filter(user=user, department__in=dep_with_prev_view_rights))
    prev_view_right_employees = [dep_mem.employee for dep_mem in dep_memberships_with_prev_view_rights]
    for employee in prev_view_right_employees:
        if employee in employees:
            employees.remove(employee)
            
    # Subtract employees who could already see schedules due to explicitly checked
    # But then were added into list beause they were a part of a department that
    # could not previously view but now can view
    explicit_prev_employees = Employee.objects.filter(user=user, id__in=emp_with_prev_view_rights)
    for employee in explicit_prev_employees:
        if employee in employees:
            employees.remove(employee)
            
    return employees                 