/*
 * JavaScript code for processing customized fullCalendar for ReScheduler
 * 
 * Author: Ryan Johnson
 */

$(document).ready(function() {
  /**
   * Selectors
   */
  var $fullCal = $("#calendar");
  var $scheduleInfo = $("#schedule-info");
  var $eligableList = $("#eligable-list");
  var $costList =  $("#cost-list");
  var $addScheduleDate = $("#add-date");
  var $addScheduleDep = $("#new-schedule-dep");
  var $conflictAssignBtn = $("#conflict-assign-btn");


  $conflictAssignBtn.on("click", _assignEmployeeAfterWarning);
      
      
  $fullCal.fullCalendar({
    editable: false,
    events: [],
    eventBackgroundColor: "transparent",
    eventTextColor: "black",
    eventBorderColor: "transparent",
        
    customButtons: {
      removeSchedule: {
        text: "Remove Schedule",
        click: remove_schedule
      },
      printCalendar: {
        text: "Print",
        click: print_calendar
      }
    },
        
    header: {
      left: "",
      center: "title",
      right: "removeSchedule printCalendar"
    },
    
    /**
     * Highlight the current clicked event, the day it belongs to, then fetch
     * the eligable list corresponding to this schedule. Also ensure the hidden
     * input add-date for adding schedules corresponds to potentially new 
     * highlighted day.
     */
    eventClick: function(calEvent, jsEvent, view) {
      // Remove any previous highlight class before highlighting this event
      $(".fc-event-clicked").removeClass("fc-event-clicked");
      $(this).find("div").addClass("fc-event-clicked");
      $(".fc-day-clicked").removeClass("fc-day-clicked");
      var date = calEvent.start.format("YYYY-MM-DD");
      $("td[data-date="+date+"]").addClass("fc-day-clicked");
      $addScheduleDate.val(date);
      
      // Make remove button active since an event is clicked
      $(".fc-removeSchedule-button").removeClass("fc-state-disabled");
      var pk = calEvent.id;
      $.get("get_schedule_info", {pk: pk}, displayEligables);
    },
        
    /** Highlight event when mouse hovers over event. */
    eventMouseover: function(calEvent, jsEvent, view) {
      var date = calEvent.start.format("YYYY-MM-DD");
      $("td[data-date="+date+"]").addClass("fc-days-event-mouseover");
    },
        
    /** De-highlight event when mouse stops hovering over event. */
    eventMouseout: function(calEvent, jsEvent, view) {
      var date = calEvent.start.format("YYYY-MM-DD");
      $("td[data-date="+date+"]").removeClass("fc-days-event-mouseover");
    },
        
    /** Mark the html elements of event with event id for later queries. */
    eventRender: function (event, element, view) {
      element.attr("id", "event-id-" + event.id);
      element.data("event-id", event.id);
    }, 
        
    /**
     * Highlight day when clicked, de-highlighted previous clicked day. Update
     * schedule adding form for date parameter to match date of the day that 
     * has just been clicked.
     */
    dayClick: function(date, jsEvent, view) {
      $curr_day_clicked = $("td[data-date="+date.format('YYYY-MM-DD')+"]");
      $prev_day_clicked = $(".fc-day-clicked");
          
      if (!$curr_day_clicked.is($prev_day_clicked)) {
        $prev_day_clicked.removeClass("fc-day-clicked");
        $curr_day_clicked.addClass("fc-day-clicked");
        
        $addScheduleDate.val(date.format("YYYY-MM-DD"));
            
        $(".fc-event-clicked").removeClass("fc-event-clicked");
        clearEligables();
        
        
        // Disable remove schedule button, no schedule selected if new day clicked
        $(".fc-removeSchedule-button").addClass("fc-state-disabled");
      }
    }
  });
      
      
  // When calendar is first loaded no schedule is slected to be removed
  $(".fc-removeSchedule-button").addClass("fc-state-disabled");
    
    
  // Turn loadSchedules into a callback function for the load-calendar-form
  $("#load-calendar-form").ajaxForm(loadSchedules); 
      
      
  /**
   * Callback for load-calendar-form which is a html get form that asks for a 
   * calendar. loadSchedules then uses the received HTTP response to update the
   * fullCalendar view, title, and events.
   */
  function loadSchedules(json_data) {
    var info = JSON.parse(json_data);
    // Get new calendar month view via date
    var format = "YYYY-MM-DDThh:mm:ss";
    var newCalDate = moment(info["date"], format);
    $fullCal.fullCalendar("gotoDate", newCalDate);
        
    // Change calendar title and schedule adding form title to new department
    var depName = $("#id_department option[value='"+info['department']+"']").text();
    $addScheduleDep.val(info["department"]);
    $(".fc-center").find("h2").text(depName + " Calendar: " + newCalDate.format("MMMM, YYYY"));
        
    // Delete any previously loaded events before displaying new events
    $fullCal.fullCalendar("removeEvents");
        
    // Get schedules and employees for loading into calendar
    var schedules = info["schedules"];
    var employees = info["employees"];
    var employeeNameDict = _employeePkToName(employees);
        
    for (var i=0;i<schedules.length;i++) {  
      var schedulePk = schedules[i]["id"];
      var startDateTime = schedules[i]["start_datetime"]; 
      var endDateTime = schedules[i]["end_datetime"];
      var hideStart = schedules[i]["hide_start_time"]; 
      var hideEnd = schedules[i]["hide_end_time"];
          
      // Get employee name for event title string
      var employeeName = "";
      var schEmployePk = schedules[i]["employee"]
      if (schEmployePk != null) {
        employeeName = employeeNameDict[schEmployePk];
      }
      var str = getEventStr(startDateTime, endDateTime, 
                            hideStart, hideEnd,
                            employeeName);
          
      // Create fullcalendar events corresponding to schedule
      var event = {
        id: schedulePk,
        title: str,
        start: startDateTime,
        end: endDateTime,
        allDay: true
        }       
      $fullCal.fullCalendar("renderEvent", event);
    }
    
    //Calculate and display calendar costs
    displayCalendarCosts(info["all_calendar_costs"], info["avg_monthly_revenue"])
        
    // Ensure calendar is visible once fully loaded
    $fullCal.css("visibility", "visible");
  }
  
  
  // Load schedule upon loading page relative to current date
  var nowDate = new Date();
  var m = nowDate.getMonth();
  var y = nowDate.getFullYear();
  
  $("#id_month").val(m + 1);
  $("#id_year").val(y);
  $("#get-calendar-button").trigger("click"); 
      
  
  /** display calendar cost li elements. */
  function displayCalendarCosts(calendarCosts, avgTotalRevenue) {
    $costList.empty();
    if (avgTotalRevenue == -1) { // -1 means no sales data currently exists
        var $li = $("<li>", {
        "id": "no-calendar-cost-data",
        "text": "There is no sales data",
        "class": "cost-list",
        }
      ).appendTo("#cost-list");
    } else {
        for (var i=0;i<calendarCosts.length;i++) { 
          var percentage = _getPercentage(calendarCosts[i]['cost'], avgTotalRevenue);
          var $li = $("<li>", {
            "id": "calendar-cost-" + calendarCosts[i]['id'],
            "text": calendarCosts[i]['name'] + ": " + percentage + "%",
            "class": "cost-list",
            "data-department-id": calendarCosts[i]['id'],
            "data-department-name": calendarCosts[i]['name'],
            "data-department-cost": calendarCosts[i]['cost'],
            }
          ).appendTo("#cost-list");
        }
    }
    // Save data on avg total revenue to ul cost-list element
    $costList.data("avg-total-revenue", avgTotalRevenue);
  }
  
  
  /** Calculate the change of cost to a calendar via data attr. */
  function addCostChange(costChange) {
    var avgMonthlyRev = $costList.data("avg-total-revenue");
    if (avgMonthlyRev != -1) { // -1 means no sales data currently exists
      var updateList = [costChange["id"], 'all']; // List of cost-li we will update
      // Set new cost and text for appropriate cost-li
      for (var i=0;i<updateList.length;i++) { 
        var $departmentCostLi = $("#calendar-cost-" + updateList[i]);
        var oldCost = $departmentCostLi.data("department-cost");
        var newCost = oldCost + costChange["cost"];
        $departmentCostLi.data("department-cost", newCost);
        percentage = _getPercentage(newCost, avgMonthlyRev);
        $departmentCostLi.text($departmentCostLi.data("department-name") + ": " + percentage + "%");
      }
    }
  }
      
  
  /** Compute percentage of two numbers and convert to integer format. */ 
  function _getPercentage(numerator, denominator) {
    return Math.round((numerator / denominator) * 100);
  }
  
  
  /**
   * Given an HTTP response of employee objects, create a mapping from employee
   * pk to employee name for quick access for employee names.
   */
  function _employeePkToName(employees) {
    var EmployeePkDict = {};
    for (var i=0; i < employees.length; i++) {
      var employeePk = employees[i]["id"];
      var employeeName = employees[i]["first_name"];
      EmployeePkDict[employeePk] = employeeName;
    }
    return EmployeePkDict;
  }
  
  
  /**
   * Concatenate strings for start time, end time, and employee name (if the
   * the schedule has an employee assigned). start and end are javascript 
   * moment objects.
   */
  function getEventStr(start, end, hideStart, hideEnd, employeeName) {
    var startStr = "?";
    if (!hideStart) {
       var startDateTime = moment(start);
       startStr = startDateTime.format("h:mm");
    }
    
    var endStr = "?";
    if (!hideEnd) {
       var endDateTime = moment(end);
       endStr = endDateTime.format("h:mm");
    }
    
    var employeeStr = "";
    if (employeeName) {
      employeeStr = ": " + employeeName;
    }
      
    var str = startStr + " - " + endStr + employeeStr;
    return str;
  }
      
      
  /** 
   * Given HTTP response, process eligable list data and create eligable list
   * of employees. If schedule has an employee already assigned, highlight that
   * employee as clicked in the eligable list.
   */    
  function displayEligables(data) {
    console.log(data);
    clearEligables();
    $scheduleInfo.css("visibility", "visible");

    var info = JSON.parse(data);
    var eligableList = info["eligable_list"];
    var schedulePk = info["schedule"]["id"];
    var currAssignedEmployeeID = info["schedule"]["employee"];
   
    // Create li corresponding to eligable employees for selected schedule
    for (var i=0;i<eligableList.length;i++) {  
      var warningStr = _compileConflictWarnings(eligableList[i]['availability']);
      var warningFlag = _compileConflictFlags(eligableList[i]['availability']);
      var name = eligableList[i]['employee'].first_name + " " +  eligableList[i]['employee'].last_name  + " " +  warningFlag;
      var $li = $("<li>", {
        "id": eligableList[i]['employee']['id'], 
        "text": name,
        "class": "eligable-list",
        "data-employee-pk": eligableList[i]['employee'].id,
        "data-schedule-pk": schedulePk,
        "data-warning-str": warningStr,
        }
      ).on("click", eligableClick
      ).appendTo("#eligable-list");
    }
    
    // If employee assigned to schedule add highlight class to appropriate li
    _highlightAssignedEmployee(currAssignedEmployeeID);
  }
  
  
  /** Given availability object, compile all conflict flags */
  function _compileConflictFlags(availability) {
    var warningFlagList = [];
    
    if (availability['(S)'].length > 0) {
      warningFlagList.push("S")
    }
    if (availability['(V)'].length > 0) {
      warningFlagList.push("V")
    }
    if (availability['(U)'].length > 0) {
      warningFlagList.push("U")
    }
    if (availability['(O)']) {
      warningFlagList.push("O")
    }
    if (warningFlagList.length > 0) {
      var warningFlag = "("
      
      for (i = 0; i < warningFlagList.length - 1; i++) {
        warningFlag += warningFlagList[i] + ", ";
      }
      warningFlag = warningFlag + warningFlagList[warningFlagList.length-1] + ")"
      return warningFlag;
    } else {
      return "";
    }
  }
  
  
  /** Given availability object, compile all conflicts into readable string. */
  function _compileConflictWarnings(availability) {
    var warningStr = "";
    
    if (availability['(S)'].length > 0) {
      warningStr += "<p>The employee is assigned to the following schedules that overlap:</p>";
      for (schedule of availability['(S)']) {
        var str = _scheduleConflictToStr(schedule);
        warningStr += "<p>" + str + "</p>";
      }
    }
    
    return warningStr;
  }
  
  
  /** Helper function to translate a schedule into warning string. */ 
  function _scheduleConflictToStr(schedule) {
    var str = "Department "
    str += $("#cal-department-selector > option:nth-child("+schedule.department+")").text();
    
    var startDate = moment(schedule.start_datetime);
    str += startStr = startDate.format(" on MMMM Do, YYYY: ");
    
    time_and_employee = getEventStr(schedule.start_datetime, schedule.end_datetime, 
                                    false, false, null);              
    str += time_and_employee;
    return str
  }
  
  
  /** Clear out eligable list and hide the schedule info section */
  function clearEligables() {
    $eligableList.empty();
    $scheduleInfo.css("visibility", "hidden");
  }
    
    
  /** 
   * Given an employee id, highlight eligable li element with corresponding
   * employee id, de-highlighting all other eligable li.
   */     
  function _highlightAssignedEmployee(employeeID) {
    $(".curr-assigned-employee").removeClass("curr-assigned-employee");
    $("#" + employeeID).addClass("curr-assigned-employee");
  }

    
  /**
   * Tell server to assign employee to schedule, create warning if conflict 
   * exists to inform user of any conflicts and allow a dialog for user to
   * decide if they wish to assign employee to schedule or not.
   */       
  function eligableClick(event) {
    //TODO: Assert that empPk != schedule.employee_id, if so, do nothing.
    var $eligableLi = $(this);
    var warningStr = $eligableLi.attr("data-warning-str");
    
    if (warningStr) {
      _eligableWarning(this, warningStr);
    } else {
      var empPk = $eligableLi.attr("data-employee-pk");
      var schPk = $eligableLi.attr("data-schedule-pk");
      $.post("add_employee_to_schedule",
             {employee_pk: empPk, schedule_pk: schPk},
             updateScheduleView);
    }
  }
  
  
  /** Display yes/no dialogue displaying all conflicts between employee & schedules */
  function _eligableWarning(eligableLi, warningStr) {
    // Set the data-employee-pk and data-schedule-pk in button for callback
    var empPk = $(eligableLi).attr("data-employee-pk");
    var schPk = $(eligableLi).attr("data-schedule-pk");
    $conflictAssignBtn.data("schedule-pk", schPk);
    $conflictAssignBtn.data("employee-pk", empPk);
    
    // Display conflicts between schedule and employee in modal body
    $conflictManifest = $("#conflict-manifest");
    $conflictManifest.empty();
    $conflictManifest.append(warningStr);
    
    // Show conflict warning modal
    $conflictModal = $("#confirmationModal");
    $conflictModal.css("margin-top", Math.max(0, ($(window).height() - $conflictModal.height()) / 2));
    $conflictModal.modal('show');
  }
  
  
  /** Assign employee to schedule after user clicks okay for warning modal */
  function _assignEmployeeAfterWarning(event) { 
    var empPk = $(this).data("employee-pk");
    var schPk = $(this).data("schedule-pk");
    $.post("add_employee_to_schedule",
           {employee_pk: empPk, schedule_pk: schPk},
           updateScheduleView);
  }
    

  /**
   * Given a successful HTTP response update event string to reflect newly
   * assigned employee.
   */
  function updateScheduleView(data) {
    var info = JSON.parse(data);
    var schedulePk = info["schedule"]["id"];
    var startDateTime = info["schedule"]["start_datetime"]; 
    var endDateTime = info["schedule"]["end_datetime"];
    var hideStart = info["schedule"]["hide_start_time"];
    var hideEnd = info["schedule"]["hide_end_time"];
    var employee = info["employee"]["first_name"];
    var str = getEventStr(startDateTime, endDateTime,
                          hideStart, hideEnd,
                          employee);
    // If employee assigned to schedule add highlight class to appropriate li
    _highlightAssignedEmployee(info["employee"]["id"]);
    // Update title string to reflect changes to schedule
    $event = $fullCal.fullCalendar("clientEvents", schedulePk);
    $event[0].title = str;
    // Update cost display to reflect any cost changes
    addCostChange(info["cost_delta"]);
    // Update then rehighlight edited schedule
    $fullCal.fullCalendar("updateEvent", $event[0]);
    var $event_div = $("#event-id-" + $event[0].id).find(".fc-content");
    $event_div.addClass("fc-event-clicked"); 
  }
    
    
  // Turn addNewSchedules into a callback function for the schedule-add-form
  $("#schedule-add-form").ajaxForm(addNewSchedule); 
     
     
  /**
   * Callback for schedule-add-form which is an html post form that tells the
   * server to create a new schedule given its form values. addNewSchedule
   * parses the successful HTTP response and creates a corresponding
   * fullCalendar event.
   */
  function addNewSchedule(json_schedule) {
    var json_schedule = JSON.parse(json_schedule);
    var schedulePk = json_schedule["id"];
    var startDateTime = json_schedule["start_datetime"]; 
    var endDateTime = json_schedule["end_datetime"];
    var hideStart = json_schedule["hide_start_time"];
    var hideEnd = json_schedule["hide_end_time"];
    var str = getEventStr(startDateTime, endDateTime,
                          hideStart, hideEnd,
                          null);
      
    var event = {
      id: schedulePk,
      title: str,
      start: startDateTime,
      end: endDateTime,
      allDay: true
    }       
    $fullCal.fullCalendar("renderEvent", event);
    //Highlight newly created event
    $(".fc-event-clicked").removeClass("fc-event-clicked");
    var $event_div = $("#event-id-" + schedulePk).find(".fc-content");
    $event_div.addClass("fc-event-clicked"); 
    // Get eligables for this new schedule
    $.get("get_schedule_info", {pk: schedulePk}, displayEligables);
    // Enable remove button, new schedule is selected
    $(".fc-removeSchedule-button").removeClass("fc-state-disabled");
  }
    
   

  /** Tell server to remove schedule given its primary key. */
  function remove_schedule() {
    var delete_schedule = confirm("Delete Schedule?");
      
    if (delete_schedule) {
      event_id = $(".fc-event-clicked").parent().data("event-id");
      if (event_id) {
        $.post("remove_schedule", 
               {schedule_pk: event_id}, 
               remove_event_after_delete);
      }
    }
  }
    
    
  /**
   * Given successful response for deleting schedule, remove corresponding
   * event from fullCalendar.
   */
  function remove_event_after_delete(data) {
    var info = JSON.parse(data);
    var schedulePk = info["schedule_pk"];
    $fullCal.fullCalendar("removeEvents", schedulePk);
    // Clear out eligable list
    $eligableList.empty();
    $scheduleInfo.css("visibility", "hidden");
    // Disable remove button since no schedule will be selected after delete
    $(".fc-removeSchedule-button").addClass("fc-state-disabled");
    // Update cost display to reflect any cost changes
    addCostChange(info["cost_delta"]);
  }
    
  
  /** Callback function for user to print calendar via print button on page */
  function print_calendar() {
    window.print();
  }
  
    
  // Create start and end time-pickers for adding schedules
  var $startTimePicker = $("#start-timepicker").pickatime();
  var $endTimePicker = $("#end-timepicker").pickatime();
    
  // Set default start and end time for time-pickers
  var st_picker = $startTimePicker.pickatime("picker");
  st_picker.set("select", [8,0]);
  var et_picker = $endTimePicker.pickatime("picker");
  et_picker.set("select", [17,0]);
    
}); 
    

/** 
 * Validate request to add a new schedule. All schedules should have a date 
 * assigned. All schedules should also have its start time before its end time.
 */    
function validateAddScheduleForm() {
  var date = document.forms["addingScheduleForm"]["add_date"].value;
  if (date == "") {
    alert("Day must be selected to add schedule");
    return false;
  }
      
  var format = "YYYY-MM-DD hh:mm A"
  var start_time_str = document.forms["addingScheduleForm"]["start-timepicker"].value;
  var end_time_str = document.forms["addingScheduleForm"]["end-timepicker"].value;
  var startDateTime = moment(date + " " + start_time_str, format);
  var endDateTime = moment(date + " " + end_time_str, format);
      
  if (endDateTime.isSameOrBefore(startDateTime)) {
    alert("Schedule start time must be before its end time");
    return false;
  }
}
    
    
/** Validate request get a calendar and associated data */
function validateGetCalendarForm() {
  //TODO: Check valid years, etc.
}