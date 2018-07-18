

def get_employees_with_same_first_name(employees):
    """Return list of employee id's of employees with non-unique first names.
    
    Args:
        employees: Queryset of all employees for given user.
    Returns:
       List of all employees who have a first name that is the same as one or
       more employees.
    """
    
    employee_list = list(employees)
    same_first_names = []
    
    for emp in employee_list:
        same_name_employees = []
        for other_emp in employee_list:
            if emp.first_name == other_emp.first_name and emp.id != other_emp.id:
                same_name_employees.append(other_emp)
        # If same name not empty, some other employees have same first name
        if same_name_employees != []:
            same_name_employees.append(emp)
            for e in same_name_employees:
                same_first_names.append(e.id)
                employee_list.remove(e)
    
    return same_first_names