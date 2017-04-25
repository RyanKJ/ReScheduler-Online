$(function(){
    // Connect each employee-li to javascript callback
    $('.list-group li').click(highlightEmployeeLi);

    
    /** Load selected employee's information into appropriate forms */
    function loadEmployeeInfo(event) {
      var empPk = $(this).data("employee-id");
      $.get("get_employee_info", {employee_pk: empPk}, displayEmployees);
    }
    
    
    /** Display HTTP response of all employees for user */
    function displayEmployees(data) {
      console.log(data);
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