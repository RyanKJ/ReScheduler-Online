


def get_last_name_initial_length(employees):
    """Map employee ids to int that represents the number of chars needed to
    write last name to render a unique name string.
    
    Given that some first names of employees are not unique, the user will want
    to both be able to distinguish the names of the employee on the calendar
    and be able to keep the names as short as possible. When a first name is
    unique, the employee does not need to have their last name displayed since
    they are the only possibility. However, if 2 employees have the first name,
    ie:
    
    John Jordan
    John Johnson
    
    We need to render:
    
    John Jor
    John Joh
    
    At the minimum to distinguish these two employees. Thus the integer their 
    id's map to will be 3, because 3 characters are needed to distinguish their
    names. In the case the employees have the same first and last name, the 
    integer will be -1 indicating there is no way to distinguish them, leaving
    that choice to the front-end in choosing how to render the names.
    
    Args:
        employees: Queryset of all employees for given user.
    Returns:
        Dictionary mapping employee id's to an integer that indicates how many
        characters of the last name are needed to distinguish the employee from
        other employee(s) with the same first name.
    """
    
    