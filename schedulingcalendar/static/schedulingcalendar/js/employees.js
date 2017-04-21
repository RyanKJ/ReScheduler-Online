$(function(){
    // Connect each employee-li to javascript callback
    $('.list-group li').click(highlightEmployeeLi);

    
    /** Load selected employee's information into appropriate forms */
    function loadEmployeeInfo(event) {
      $.get("get_employees", displayEmployees);
    }
    
    
    /** Display HTTP response of all employees for user */
    function displayEmployees() {
      // Given a serialized object of employee, put stuff into fields
    }
    
    
    /** Highlight employee li if successfully loaded. */ 
    function highlightEmployeeLi(event) {
        event.preventDefault();
        
        $employee_li = $(this);
        $employee_li.parent().find('li').removeClass('active');
        $employee_li.addClass('active');
    }
    
    
    
})