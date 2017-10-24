/*
 * JavaScript code for processing customized fullCalendar for ReScheduler
 * 
 * Author: Ryan Johnson
 */

$(document).ready(function() {
  /**
   * Selectors And Variables
   */
  var $fullCal = $("#calendar");
  var $scheduleInfo = $("#schedule-info");
  var $addScheduleDate = $("#add-date");
  var $addScheduleDep = $("#new-schedule-dep");
  var $conflictAssignBtn = $("#conflict-assign-btn");
  var WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday"]
  var displaySettings = {};
  var $calendarLoaderForm = $("#load-calendar-form");
  
  $fullCal.fullCalendar({
    editable: false,
    events: [],
    eventBackgroundColor: "transparent",
    eventTextColor: "black",
    eventBorderColor: "transparent",
        
    customButtons: {
      printCalendar: {
        text: "Print",
        click: print_calendar
      }
    },
        
    header: {
      left: "",
      center: "title",
      right: "printCalendar"
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
      $(".fc-swapSchedule-button").removeClass("fc-state-disabled");
      var pk = calEvent.id;
      // TODO Add get employee's to swap with
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
        // Disable remove schedule button, no schedule selected if new day clicked
        $(".fc-swapSchedule-button").addClass("fc-state-disabled");
      }
    }
  });
      
  // When calendar is first loaded no schedule is selected to be removed
  // so we disable the remove button.
  $(".fc-swapSchedule-button").addClass("fc-state-disabled");
    
  // Turn loadSchedules into a callback function for the load-calendar-form
  var options = {success: loadSchedules,
                 error: calendarNotFoundError}
  $("#load-calendar-form").ajaxForm(options); 
  
      
  /**
   * Callback for load-calendar-form which is a html get form that asks for a 
   * calendar. loadSchedules then uses the received HTTP response to update the
   * fullCalendar view, title, and events.
   */
  function loadSchedules(json_data) {
    console.log("successful response")
    var info = JSON.parse(json_data);
    console.log(info);
    // Save display settings for calendar events
    displaySettings = info["display_settings"]
    
    // Get new calendar month view via date
    var format = "YYYY-MM-DDThh:mm:ss";
    var newCalDate = moment(info["date"], format);
    $fullCal.fullCalendar("gotoDate", newCalDate);
        
    // Change calendar title and schedule adding form title to new department
    var depName = $calendarLoaderForm.data("department-name");
    var cal_title = depName + " Calendar: " + newCalDate.format("MMMM, YYYY") + " Version " + info["version"];
    $(".fc-center").find("h2").text(cal_title);
        
    // Delete any previously loaded events before displaying new events
    $fullCal.fullCalendar("removeEvents");
        
    // Get schedules and employees for loading into calendar
    var schedules = info["schedules"];
    var employees = info["employees"];
    var employeeNameDict = _employeePkToName(employees);

    // Collection of events to be rendered together
    var events = [];
        
    for (var i=0;i<schedules.length;i++) {  
      var schedulePk = schedules[i]["id"];
      var startDateTime = schedules[i]["start_datetime"]; 
      var endDateTime = schedules[i]["end_datetime"];
      var hideStart = schedules[i]["hide_start_time"]; 
      var hideEnd = schedules[i]["hide_end_time"];
          
      // Get employee name for event title string
      var firstName = "";
      var lastName = "";
      var schEmployePk = schedules[i]["employee"]
      if (schEmployePk != null) {
        firstName = employeeNameDict[schEmployePk]["firstName"];
        lastName = employeeNameDict[schEmployePk]["lastName"];
      }
      var str = getEventStr(startDateTime, endDateTime, 
                            hideStart, hideEnd,
                            firstName, lastName); 
      // Create fullcalendar event corresponding to schedule
      var event = {
        id: schedulePk,
        title: str,
        start: startDateTime,
        end: endDateTime,
        allDay: true
        }       
      events.push(event);
    }
    // Render event collection
    $fullCal.fullCalendar("renderEvents", events);

    // Ensure calendar is visible once fully loaded
    $fullCal.css("visibility", "visible");
  }
  
  
  /**
   * Callback where user queries for calendar that does not exist
   */
  function calendarNotFoundError(jqXHR, exception) {
    // Clear any events to indicate no calendar for this date
    $fullCal.fullCalendar("removeEvents");
    
    // Ensure calendar is visible
    $fullCal.css("visibility", "visible");
    
    // Set calendar title to indicate it does not exist
    var cal_title = jqXHR.responseText
    $(".fc-center").find("h2").text(cal_title);
    
    // Show no calendar alert modal
    $noCalendarModal = $("#noCalendarModal");
    $noCalendarModal.css("margin-top", Math.max(0, ($(window).height() - $noCalendarModal.height()) / 2));
    $noCalendarModal.modal('show');
  }
  
  
  // Load schedule upon loading page relative to current date
  var liveCalDate = new Date($calendarLoaderForm.data("date"));
  var m = liveCalDate.getMonth() + 1; //Moment uses January as 0, Python as 1
  var y = liveCalDate.getFullYear();
  var department = $calendarLoaderForm.data("department");
  var version = $calendarLoaderForm.data("live-cal-version");
  
  $("#id_month").val(m + 1);
  $("#id_year").val(y);
  $("#id_department").val(department);
  $("#id_version").val(version);
  
  console.log("version is: ");
  console.log(version);
  
  $("#get-calendar-button").trigger("click"); 
    
  
  /**
   * Given an HTTP response of employee objects, create a mapping from employee
   * pk to employee name for quick access for employee names.
   */
  function _employeePkToName(employees) {
    var EmployeePkDict = {};
    for (var i=0; i < employees.length; i++) {
      var employeePk = employees[i]["id"];
      var firstName = employees[i]["first_name"];
      var lastName = employees[i]["last_name"];
      EmployeePkDict[employeePk] = {"firstName": firstName,
                                    "lastName": lastName};
    }
    return EmployeePkDict;
  }
  
  
  /**
   * Concatenate strings for start time, end time, and employee name (if the
   * the schedule has an employee assigned). start and end are javascript 
   * moment objects.
   */
  function getEventStr(start, end, hideStart, hideEnd, firstName, lastName) {
    // Construct time format string based off of display settings
    var displayMinutes = displaySettings["display_minutes"];
    var displayAMPM = displaySettings["display_am_pm"];
    timeFormat = "h"
    if (displayMinutes) { timeFormat += ":mm"; }
    if (displayAMPM) { timeFormat += " a"; }
    // Name display settings
    var displayLastNames = displaySettings["display_last_names"]; 
    var displayLastNameFirstChar = displaySettings["display_first_char_last_name"]; 
    
    // Construct time strings
    var startStr = "?";
    if (!hideStart) {
       var startDateTime = moment(start);
       startStr = startDateTime.format(timeFormat);
    }
    var endStr = "?";
    if (!hideEnd) {
       var endDateTime = moment(end);
       endStr = endDateTime.format(timeFormat);
    }
    // Construct name string
    var employeeStr = "";
    if (firstName) {
      employeeStr = ": " + firstName;
      if (displayLastNames && lastName) {
        if (displayLastNameFirstChar) {
          employeeStr += " " + lastName.charAt(0);
        } else {
          employeeStr += " " + lastName;
        }
      }
    }
      
    var str = startStr + " - " + endStr + employeeStr;
    return str;
  }
    
  
  /** Callback function for user to print calendar via print button on page */
  function print_calendar() {
    window.print();
  }
});

/** Validate request get a calendar and associated data */
function validateGetCalendarForm() {
  //TODO: Check valid years, etc.
}