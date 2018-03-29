/*
 * JavaScript code for processing customized fullCalendar for ReScheduler
 * 
 * Author: Ryan Johnson
 */

$(document).ready(function() {
  /**
   * Selectors And Variables
   */
  // Constant variables
  var WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday"];
  var DATE_FORMAT = "YYYY-MM-DD";
  var EMPLOYEELESS_EVENT_ROW = 1000;
                  
  // General state variables
  var calDate = null;
  var calDepartment = null;
  var calActive = null;
  var displaySettings = {};
  var employeeNameDict = {};
  var departmentCosts = {};
  var avgMonthlyRev = -1;
  var dayNoteHeaders = {};
  var dayNoteBodies = {};
  var scheduleNotes = {};
  var employeeRowList = [];
  var copySchedulePksList = [];
  
  // Jquery object variables
  var $fullCal = $("#calendar");
  var $scheduleInfo = $("#schedule-info");
  var $eligableList = $("#eligable-list");
  var $calendarLoaderForm = $("#load-calendar-form");
  var $conflictAssignBtn = $("#conflict-assign-btn");
  var $removeScheduleBtn = $("#remove-btn");
  var $removeBtnConfirm = $("#remove-btn-confirm")
  var $removeBtnConfirmContainer = $("#remove-btn-confirm-container");
  var $editScheduleBtn = $("#edit-btn");
  var $costList =  $("#cost-list");
  var $addScheduleDate = $("#add-date");
  var $addScheduleDep = $("#new-schedule-dep");
  var $viewLiveDate = $("#view-live-date");
  var $viewLiveDep = $("#view-live-department");
  var $pushLive = $("#push-live");
  var $pushLiveAfterWarning = $("#push-calendar-after-warning-btn");
  var $deactivateLiveAfterWarning = $("#deactivate-warning-btn");
  var $reactivateLiveAfterWarning = $("#reactivate-warning-btn");
  var $successfulLiveCalMsg = $("#successful-live-cal-change");
  var $setActiveLive = $("#active-live-set");
  var $viewLive = $("#view-live");
  var $eligibleLegendSelector = $("#legend-selector");
  var $startTimePicker = $("#start-timepicker").pickatime();
  var $endTimePicker = $("#end-timepicker").pickatime();
  var $hideStart = $("#start-checkbox");
  var $hideEnd = $("#end-checkbox");
  var $copyDayBtn = $("#copy-day");
  var $dayNoteBtn = $("#day-note");
  var $dayNoteHeaderBtn = $("#day-note-header-btn");
  var $dayNoteHeaderText = $("#id_header_text");
  var $dayNoteBodyBtn = $("#day-note-body-btn");
  var $dayNoteBodyText = $("#id_body_text");
  var $scheduleNoteBtn = $("#schedule-note-btn");
  var $scheduleNoteText = $("#id_schedule_text");
  
  // Start and end schedule time pickers
  var st_picker = $startTimePicker.pickatime("picker");
  var et_picker = $endTimePicker.pickatime("picker");
    
  $conflictAssignBtn.click(_assignEmployeeAfterWarning);
  $removeScheduleBtn.click(removeSchedule);
  $removeBtnConfirm.click(_removeScheduleAfterWarning);
  $editScheduleBtn.click(editSchedule);
  $pushLive.click(pushCalendarLive);
  $pushLiveAfterWarning.click(_pushCalendarAfterWarning);
  $deactivateLiveAfterWarning.click(_SetActivityAfterWarning);
  $reactivateLiveAfterWarning.click(_SetActivityAfterWarning);
  $setActiveLive.click(SetActiveLiveCalendar);
  $dayNoteBtn.click(showDayNoteModal);
  $eligibleLegendSelector.click(showEligibleLegend);
  $dayNoteHeaderBtn.click(postDayNoteHeader);
  $dayNoteBodyBtn.click(postDayNoteBody);
  $scheduleNoteBtn.click(postScheduleNote);
  $copyDayBtn.click(copySchedulePks);
  
  var toolbar = document.getElementById("toolbar-sticky");
  var sticky = toolbar.offsetTop;
  window.onscroll = function() { stickyToolbar(); };
  
  $fullCal.fullCalendar({
    fixedWeekCount: false,
    editable: false,
    events: [],
    eventBackgroundColor: "transparent",
    eventTextColor: "black",
    eventBorderColor: "transparent",  
    eventOrder: "customSort,eventRowSort,title",
    header: {
      left: "",
      center: "title",
      right: ""
    },
    
    /**
     * Highlight the current clicked event, the day it belongs to, then fetch
     * the eligable list corresponding to this schedule. Also ensure the hidden
     * input add-date for adding schedules corresponds to potentially new 
     * highlighted day.
     */
    eventClick: function(calEvent, jsEvent, view) {
      $(".fc-day-clicked").removeClass("fc-day-clicked");
      var date = calEvent.start.format(DATE_FORMAT);
      $("td[data-date="+date+"]").addClass("fc-day-clicked");
      $addScheduleDate.val(date);
      // Reset remove confirm
      $removeScheduleBtn.css("display", "block");
      $removeBtnConfirmContainer.css("display", "none");
      
      // Update text field for editing day note
      if (dayNoteHeaders.hasOwnProperty(date)) {
        dayNoteHeaderText = dayNoteHeaders[date]["header_text"];
        $dayNoteHeaderText.val(dayNoteHeaderText);
      } else {
        $dayNoteHeaderText.val(""); // No note exists, reset text field
      }
      if (dayNoteBodies.hasOwnProperty(date)) {
        dayNoteBodyText = dayNoteBodies[date]["body_text"];
        $dayNoteBodyText.val(dayNoteBodyText);
      } else {
        $dayNoteBodyText.val(""); // No note exists, reset text field
      }
      $(".fc-event-clicked").removeClass("fc-event-clicked");
      if (calEvent.isSchedule) {
        $(this).find("div").addClass("fc-event-clicked");
        var pk = calEvent.id;
        // Set text field for this schedule in schedule note form
        var scheduleNote = scheduleNotes[pk];
        $scheduleNoteText.val(scheduleNote);
        $scheduleNoteBtn.prop('disabled', false);
        // Get eligibles for this schedule
        $.get("get_schedule_info", {pk: pk}, displayEligables);
      } else { //Non-schedule fc-event was clicked
        clearEligables();
        $scheduleNoteText.val("Please Select A Schedule First");
        $scheduleNoteBtn.prop('disabled', true);
      }
    },
        
    /** Highlight event when mouse hovers over event. */
    eventMouseover: function(calEvent, jsEvent, view) {
      var date = calEvent.start.format(DATE_FORMAT);
      $("td[data-date="+date+"]").addClass("fc-days-event-mouseover");
    },
        
    /** De-highlight event when mouse stops hovering over event. */
    eventMouseout: function(calEvent, jsEvent, view) {
      var date = calEvent.start.format(DATE_FORMAT);
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
      var formatted_date = date.format(DATE_FORMAT);
      $curr_day_clicked = $("td[data-date="+formatted_date+"]");
      $prev_day_clicked = $(".fc-day-clicked");
          
      if (!$curr_day_clicked.is($prev_day_clicked)) {
        $prev_day_clicked.removeClass("fc-day-clicked");
        $curr_day_clicked.addClass("fc-day-clicked");
        // Reset remove confirm
        $removeScheduleBtn.css("display", "block");
        $removeBtnConfirmContainer.css("display", "none");
        
        $addScheduleDate.val(formatted_date);
            
        $(".fc-event-clicked").removeClass("fc-event-clicked");
        clearEligables();
        
        // Update text field for editing day notes
        if (dayNoteHeaders.hasOwnProperty(formatted_date)) {
          dayNoteHeaderText = dayNoteHeaders[formatted_date]["header_text"];
          $dayNoteHeaderText.val(dayNoteHeaderText);
        } else {
          $dayNoteHeaderText.val(""); // No note exists, reset text field
        }
        if (dayNoteBodies.hasOwnProperty(formatted_date)) {
          dayNoteBodyText = dayNoteBodies[formatted_date]["body_text"];
          $dayNoteBodyText.val(dayNoteBodyText);
        } else {
          $dayNoteBodyText.val(""); // No note exists, reset text field
        }
        $scheduleNoteText.val("Please Select A Schedule First");
        $scheduleNoteBtn.prop('disabled', true);
      }
    }
  });
  
  
  // Turn loadSchedules into a callback function for the load-calendar-form
  $("#load-calendar-form").ajaxForm(loadSchedules); 
  
      
  /**
   * Callback for load-calendar-form which is a html get form that asks for a 
   * calendar. loadSchedules then uses the received HTTP response to update the
   * fullCalendar view, title, and events.
   */
  function loadSchedules(json_data) {
    // Clear out eligable list incase previous calendar was loaded
    $eligableList.empty();
    $scheduleInfo.css("display", "none");
    employeeRowList = [];
    _removeDayNoteHeaders();
    
    var info = JSON.parse(json_data);
    // Save display settings for calendar events
    displaySettings = info["display_settings"]
    
    // Let user know if no employees exist at all via modal
    if (info["no_employees_exist"]) {
      _showEmployeelessModal();
    } else {
      if (info["no_employees_exist_for_department"]) {
        _showEmployeelessDepartmentModal();
      }
    }
    // Set default start and end time for time-pickers
    st_picker.set("select", displaySettings["schedule_start"], { format: 'HH:i' });
    et_picker.set("select", displaySettings["schedule_end"], { format: 'HH:i' });
    $hideStart.prop('checked', displaySettings["hide_start"]);
    $hideEnd.prop('checked', displaySettings["hide_end"]);
    
    // Get new calendar month view via date
    calDate = moment(info["date"], DATE_FORMAT);
    $fullCal.fullCalendar("gotoDate", calDate);
    $viewLiveDate.val(calDate.format(DATE_FORMAT));
    
    // Change calendar title and schedule adding form title to new department
    calDepartment = info['department'];
    var depName = $("#id_department option[value='"+calDepartment+"']").text();
    $addScheduleDep.val(calDepartment);
    $viewLiveDep.val(calDepartment);
    $(".fc-center").find("h2").text(depName + ": " + calDate.format("MMMM, YYYY"));
        
    // Delete any previously loaded events before displaying new events
    $fullCal.fullCalendar("removeEvents");
        
    // Get schedules, employees, and notes for loading into calendar
    var schedules = info["schedules"];
    var employees = info["employees"];
    employeeNameDict = _employeePkToName(employees);
    var dayHeaderNotes = info["day_note_header"];
    var dayBodyNotes = info["day_note_body"]; 
    
    // Create fullcalendar events corresponding to schedules
    if (displaySettings["unique_row_per_employee"]) {
      var events = _schedulesToUniqueRowEvents(schedules, employeeNameDict);
    } else {
      var events = _schedulesToEvents(schedules, employeeNameDict);
    }
    
    // Collection of day body notes to be rendered as fullcalendar events
    for (var i=0;i<dayBodyNotes.length;i++) { 
      dayNoteBodies[dayBodyNotes[i]["date"]] = dayBodyNotes[i];
      if (dayBodyNotes[i]["body_text"]) { // Don't Display blank notes
        var event = {
          id:"body-note-" + dayBodyNotes[i]["date"],
          title: dayBodyNotes[i]["body_text"],
          start: dayBodyNotes[i]["date"],
          allDay: true,
          isSchedule: false,
          isNote: true,
          employeeAssigned: false,
          customSort: 1,
          eventRowSort: 2000,
          className: "blank-event bold"
        }
        events.push(event);
      }
    }
    // Render event collection
    $fullCal.fullCalendar("renderEvents", events);
    
    // Collection of day header notes to be rendered manually
    for (var i=0;i<dayHeaderNotes.length;i++) { 
      dayNoteHeaders[dayHeaderNotes[i]["date"]] = dayHeaderNotes[i];
      _dayNoteHeaderRender(dayHeaderNotes[i]);
    }
    
    //Calculate and display calendar costs
    departmentCosts = info["department_costs"];
    avgMonthlyRev = info["avg_monthly_revenue"];
    displayCalendarCosts();
    
    //Set activate/deactivate to state of live_calendar
    calActive = info["is_active"];
    setCalLiveButtonStyles();
    
    //Make other month days displayed not gray'd out
    $(".fc-other-month").removeClass("fc-other-month");
   
    // Ensure calendar is visible once fully loaded
    $fullCal.css("visibility", "visible");
    
    // Set .fc-day elements to call a function on a double click
    var $fcDays = $(".fc-day");
    $fcDays.dblclick(dblClickHelper);
  }
  
  
  /** Helper function to create fullcalendar events with unique rows */
  function _schedulesToUniqueRowEvents(schedules, employeeNameDict) {
    var scheduleEvents = [];
    var schedulesToDates = {};
    
    // Create dict of schedules where dates are the keys, schedules as values
    // Also create a list of employee pks that map index (row) to employee pk
    for (var i=0;i<schedules.length;i++) {
      var startDateTime = moment(schedules[i]["start_datetime"]);
      var startDate = startDateTime.format(DATE_FORMAT);
      if (schedulesToDates.hasOwnProperty(startDate)) {
        schedulesToDates[startDate].push(schedules[i]);
      } else {
        schedulesToDates[startDate] = [];
        schedulesToDates[startDate].push(schedules[i]);
      }
      // Create a employeeRowList mapping row numbers to employee pks
      var employeePk = schedules[i].employee;
      if (employeePk&& !employeeRowList.includes(employeePk)) {
        employeeRowList.push(employeePk);
      }
    }
    // Iterate thru each date's schedules and create appropriate events
    for (var date in schedulesToDates) {
      if(schedulesToDates.hasOwnProperty(date)) {
        var employeeAssignedOnDate = employeeRowList.slice(0);
        var schedules = schedulesToDates[date];
        var employelessSchedules = [];
        // Create events for schedules with employees
        for (var i=0;i<schedules.length;i++) {
          var schedulePk = schedules[i]["id"];
          var schEmployePk = schedules[i]["employee"];
          if (schEmployePk != null) {
            var eventRow = employeeRowList.indexOf(schEmployePk);
            var employeeRowIndex = employeeAssignedOnDate.indexOf(schEmployePk);
            if (employeeRowIndex > -1) {
              employeeAssignedOnDate.splice(employeeRowIndex, 1);
            }
            var fullCalEvent = _scheduleToFullCalendarEvent(schedules[i], employeeNameDict, eventRow)                    
            scheduleEvents.push(fullCalEvent);
          } else { // Create events for employeeless schedules
            var fullCalEvent = _scheduleToFullCalendarEvent(schedules[i], employeeNameDict, EMPLOYEELESS_EVENT_ROW)                    
            scheduleEvents.push(fullCalEvent);
          }
        }
        // Create blank events for any empty employee rows for given date
        for (var i=0;i<employeeAssignedOnDate.length;i++) {
          var eventRowEmployeePk = employeeAssignedOnDate[i];
          eventRow = employeeRowList.indexOf(eventRowEmployeePk);
          var fullCalEvent = _createBlankEvent(date, eventRowEmployeePk, eventRow);
          scheduleEvents.push(fullCalEvent);
        }  
      }
    }
    return scheduleEvents;
  }
  
  
  /** Helper function to create fullcalendar events given schedules */
  function _schedulesToEvents(schedules, employeeNameDict) {
    var scheduleEvents = [];
    // Create fullcalendar event corresponding to schedule
    for (var i=0;i<schedules.length;i++) {
      var fullCalEvent = _scheduleToFullCalendarEvent(schedules[i], employeeNameDict, 1);
      scheduleEvents.push(fullCalEvent);
    }
    return scheduleEvents;
  }
  
  
  /** Helper function to create a single full calendar event given schedule */
  function _scheduleToFullCalendarEvent(schedule, employeeNameDict, eventRow) {
    var schedulePk = schedule["id"];
    var startDateTime = schedule["start_datetime"]; 
    var endDateTime = schedule["end_datetime"];
    var hideStart = schedule["hide_start_time"]; 
    var hideEnd = schedule["hide_end_time"];
    var note = schedule["schedule_note"];
    scheduleNotes[schedulePk] = note; // For loading schedule note form field
       
    // Get employee name for event title string
    var firstName = "";
    var lastName = "";
    var isEmployeeAssigned = false;
    var schEmployePk = schedule["employee"];
    if (schEmployePk != null) {
      firstName = employeeNameDict[schEmployePk]["firstName"];
      lastName = employeeNameDict[schEmployePk]["lastName"];
      isEmployeeAssigned = true;
    }
    var str = getEventStr(startDateTime, endDateTime, hideStart, hideEnd,
                          firstName, lastName, note); 
                                             
    var fullCalEvent = {
      id: schedulePk,
      title: str,
      start: startDateTime,
      end: endDateTime,
      allDay: true,
      isSchedule: true,
      isNote: false,
      employeeAssigned: isEmployeeAssigned,
      customSort: 0,
      eventRowSort: eventRow,
      employeePk: schEmployePk
    } 
    return fullCalEvent;
  }
  
  
  /** Helper function to create a blank full calendar event */
  function _createBlankEvent(date, employeePk, eventRow) {
    var str = _getBlankEventStr(date, employeePk);
    var fullCalEvent = {
      id: date + "-" + employeePk,
      title: "",
      start: date,
      end: date,
      allDay: true,
      isSchedule: false,
      isNote: false,
      employeeAssigned: false,
      customSort: 0,
      eventRowSort: eventRow,
      employeePk: -1,
      className: "blank-event"
    }
    return fullCalEvent;
  }
  
  
  /** Helper functino to create str for blank event */
  function _getBlankEventStr(date, employeePk) {
    // 1) Given an employee we need to look at some data structure that tells 
    //    us that for this date there is a vacation/unavailability. So something
    //    like a dictionary where the keys map to an array of employee pks,
    //    (Or could be vacations, but then we'd need to search it, maybe with 
    //     a lambda function f(x) {x.employee})? So then if we find for a date
    //     an employee pk, that means on that date that employee has
    //    "Time Requested Off" and then the string becomes "**** TRO ****" or
    //    something.
    //
    //    The issue then becomes: what if the order comes off because an employee
    //    gets deleted or something? The order issue only comes from adding
    //    and editing, removing schedules, which, when the user prints a live
    //    calendar, the rows will be static
    //    So this function is dreadfully simple, the only issue is passing the
    //    dict from the backend.
  }
  
  
  /** Helper function for rendering day not headers for the full calendar */
  function _dayNoteHeaderRender(dayHeaderObj) {
    var date = dayHeaderObj["date"];
    var $dayHeader = $("thead td[data-date="+date+"]");
    var dayNumber = $dayHeader.children().first().text();
    var html = "<span class='fc-day-number day-number-of-header-note fright'>" + dayNumber + "</span>" +
               "<span class='fc-day-number fleft'><b>" + dayHeaderObj["header_text"] + "</b></span>"
    $dayHeader.html(html);
  }
  
  
  /** Helper function to remove all day note headers */
  function _removeDayNoteHeaders() {
    var $dayNumberOfHeaderNotes = $(".day-number-of-header-note");
    console.log("Remove Day Note Headers:")
    console.log($dayNumberOfHeaderNotes);
    $dayNumberOfHeaderNotes.each(function( i ) {
      var dayNumber = $(this).text();
      var html = "<span class='fc-day-number'>" + dayNumber + "</span>"
      var $dayHeader = $(this).parent();
      $dayHeader.html(html);
    });
  }
  

  // Load schedule upon loading page relative to current date
  var liveCalDate = new Date($calendarLoaderForm.data("date"));
  var m = liveCalDate.getMonth() + 1; //Moment uses January as 0, Python as 1
  var y = liveCalDate.getFullYear();
  var dep = $calendarLoaderForm.data("department");
  
  $("#id_month").val(m + 1);
  $("#id_year").val(y);
  $("#id_department").val(dep);
  $("#get-calendar-button").trigger("click"); 
  
  
  /** Show user modal asking if they want to make current calendar state live. */
  function pushCalendarLive(event) {
    $pushModal = $("#pushModal");
    $pushModal.css("margin-top", Math.max(0, ($(window).height() - $pushModal.height()) / 2));
    $pushModal.modal('show');
  }
  
  
  /** Tell server to make current calendar state live for employee queries */
  function _pushCalendarAfterWarning(event) {
    $.post("push_live",
           {department: calDepartment, date: calDate.format(DATE_FORMAT)},
            successfulCalendarPush);
  }
  
  
  /** Inform user that the calendar was succesfully pushed. */
  function successfulCalendarPush(data) {
    var info = JSON.parse(data);
    calActive = true;
    // Set styles of View Live and De/Reactivate buttons depending on state
    setCalLiveButtonStyles();
    var msg = info["message"];
    successfulLiveCalStateChange(msg);
  }
  
  
  /** Show user modal to indicate successful change to live calendar */
  function successfulLiveCalStateChange(msg) {
    $successfulLiveCalMsg.text(msg);
    $successfulPushModal = $("#successfulPushModal");
    $successfulPushModal.css("margin-top", Math.max(0, ($(window).height() - $successfulPushModal.height()) / 2));
    $successfulPushModal.modal('show');
  }
  
  
  /** 
   * Warn user about changing active state of live calendar. If user still
   * clicks okay, commit change to the activity state of the live calendar.
   */
  function SetActiveLiveCalendar(event) {
    // Check to see if live calendar exists for date/dep
    if(calActive !== null) {
      // Show user warning modal before committing to change with live calendar
      if (calActive) {
        $deactivateModal = $("#deactivateLive");
        $deactivateModal.css("margin-top", Math.max(0, ($(window).height() - $deactivateModal.height()) / 2));
        $deactivateModal.modal('show');
      } else {
        $reactivateModal = $("#reactivateLive");
        $reactivateModal.css("margin-top", Math.max(0, ($(window).height() - $reactivateModal.height()) / 2));
        $reactivateModal.modal('show');
      }
    }
  }
  
  
  /** Set the activity state of live calendar after warning. */
  function _SetActivityAfterWarning(event) {
    if(calActive !== null) {
      var newCalActive = true;
      // Live calendar exists, so set newCalActive to opposite of current state
      if (calActive) {
        newCalActive = false;
      }
      $.post("set_active_state",
             {department: calDepartment, date: calDate.format(DATE_FORMAT), active: newCalActive},
              successfulActiveStateSet);
    }
  }
  
  
  /** 
   * Inform user that the active state of live calendar was set and update
   * styles and state of variables representing the live calendar's state.
   */
  function successfulActiveStateSet(data) {
    var info = JSON.parse(data);
    var msg = info["message"];
    calActive = info["is_active"];
    // Set styles of View Live and De/Reactivate buttons depending on state
    setCalLiveButtonStyles();
    successfulLiveCalStateChange(msg);
  }
  
  
  /** Set styles of view live and De/Reactivate Live buttons given active state */
  function setCalLiveButtonStyles() {
    if (calActive == null) {
      $setActiveLive.addClass("unactive-live");
      $setActiveLive.text("Reactivate Live");
      $viewLive.addClass("unactive-live");
      $viewLive.prop('disabled', true);
    }
    if (!calActive && calActive !== null) {
      $setActiveLive.removeClass("unactive-live");
      $setActiveLive.text("Reactivate Live");
      $viewLive.addClass("unactive-live");
      $viewLive.prop('disabled', true);
    }
    if (calActive) {
      $setActiveLive.removeClass("unactive-live");
      $setActiveLive.text("Deactivate Live");
      $viewLive.removeClass("unactive-live");
      $viewLive.prop('disabled', false);
    }
  }
    
  
  /** Display calendar cost li elements. */
  function displayCalendarCosts() {
    $costList.empty();
    if (avgMonthlyRev == -1) { // -1 means no sales data currently exists
        var $li = $("<li>", {
        "id": "no-calendar-cost-data",
        "text": "There is no sales data",
        "class": "cost-list",
        }
      ).appendTo("#cost-list");
    } else {
        for (department_key in departmentCosts) { 
          var department = departmentCosts[department_key]
          var percentage = _getPercentage(department['cost'], avgMonthlyRev);
          var $li = $("<li>", {
            "id": "calendar-cost-" + department_key,
            "text": department['name'] + ": " + percentage + "%",
            "class": "cost-list",
            }
          ).appendTo("#cost-list");
        }
    }
  }

    
  /** Compute percentage of two numbers and convert to integer format. */ 
  function _getPercentage(numerator, denominator) {
    return Math.round((numerator / denominator) * 100);
  }
  
  
  /** Calculate the change of cost to a calendar */
  function addCostChange(costChange) {
    if (avgMonthlyRev != -1) { // -1 means no sales data currently exists
      for (department_key in costChange) { 
        // Get new cost of department
        var department = departmentCosts[department_key];
        var oldCost = department['cost'];
        var newCost = oldCost + costChange[department_key];
        department['cost'] = newCost;
        // Set new cost and text for appropriate cost-li
        percentage = _getPercentage(newCost, avgMonthlyRev);
        var $departmentCostLi = $("#calendar-cost-" + department_key);
        $departmentCostLi.text(department['name'] + ": " + percentage + "%");
      }
    }
  }
    
  
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
  function getEventStr(start, end, hideStart, hideEnd, firstName, lastName, note) {
    // Construct time string based off of display settings
    var displayMinutes = displaySettings["display_minutes"];
    var displayNonzeroMinutes = displaySettings["display_nonzero_minutes"];
    var displayAMPM = displaySettings["display_am_pm"];
    
    timeFormat = "h"
    if (displayMinutes && !displayNonzeroMinutes) { timeFormat += ":mm"; }
    if (displayAMPM) { timeFormat += " a"; }
     
    // Construct time strings
    var startStr = "?";
    if (!hideStart) {
      var startDateTime = moment(start);
      if (displayNonzeroMinutes && startDateTime.minute() != 0) {
        onlyNonZeroTimeFormat = "h:mm";
        if (displayAMPM) { onlyNonZeroTimeFormat += " a"; }
        startStr = startDateTime.format(onlyNonZeroTimeFormat);
      } else {
        startStr = startDateTime.format(timeFormat);
      }
    }
    var endStr = "?";
    if (!hideEnd) {
       var endDateTime = moment(end);
       if (displayNonzeroMinutes && endDateTime.minute() != 0) {
          onlyNonZeroTimeFormat = "h:mm";
          if (displayAMPM) { onlyNonZeroTimeFormat += " a"; }
          endStr = endDateTime.format(onlyNonZeroTimeFormat);
       } else {
          endStr = endDateTime.format(timeFormat);
       }
    }
    
    // Construct employee name string based off of display settings
    var displayLastNames = displaySettings["display_last_names"]; 
    var displayLastNameFirstChar = displaySettings["display_first_char_last_name"]; 
    
    var employeeStr = "";
    if (firstName) {
      employeeStr = ": " + firstName;
      if (displayLastNameFirstChar && lastName) {
        employeeStr += " " + lastName.charAt(0);
      }
      if (displayLastNames && lastName && !displayLastNameFirstChar) {
        employeeStr += " " + lastName;
      }
    }
    
    // Combine time and name strings to full construct event string title
    var str = startStr + " - " + endStr + employeeStr;
    if (note) {
      str += " " + note;
    }
    return str;
  }
      
      
  /** 
   * Given HTTP response, process eligable list data and create eligable list
   * of employees. If schedule has an employee already assigned, highlight that
   * employee as clicked in the eligable list.
   */    
  function displayEligables(data) {
    clearEligables();
    $scheduleInfo.css("display", "block");
    
    var info = JSON.parse(data);
    var eligableList = info["eligable_list"];
    if (displaySettings["sort_by_names"]) {
      eligableList.sort(compareEmployeeName);
    }
    // Get schedule pk, employee, and schedule duration
    var schedule = info["schedule"]
    var schedulePk = schedule["id"];
    var currAssignedEmployeeID = schedule["employee"];
    var start = moment(schedule['start_datetime']);
    var end = moment(schedule['end_datetime']);
    var duration = moment.duration(end.diff(start));
    var schedule_hours = duration.asHours();
    // Create li corresponding to eligable employees for selected schedule
    for (var i=0;i<eligableList.length;i++) {  
      var warningStr = _compileConflictWarnings(eligableList[i]['availability']);
      var warningFlag = _compileConflictFlags(eligableList[i]['availability']);
      var eligableColorClasses = _compileColorClasses(eligableList[i]['employee'], 
                                                      eligableList[i]['availability']);
      var name = eligableList[i]['employee'].first_name + " " +  eligableList[i]['employee'].last_name  + " " +  warningFlag;  
      var $li = $("<li>", {
        "id": eligableList[i]['employee']['id'], 
        "class": eligableColorClasses,
        "data-employee-pk": eligableList[i]['employee'].id,
        "data-schedule-pk": schedulePk,
        "data-warning-str": warningStr,
        "click": eligableClick,
        }
      ).appendTo("#eligable-list");
      // Create content inside each eligible li
      var desired_hours_title = "Desired Hours: " + eligableList[i]['employee']['desired_hours'];
      var curr_hours = eligableList[i]['availability']['Hours Scheduled'];
      if (currAssignedEmployeeID != eligableList[i]['employee']['id']) {
        curr_hours -= schedule_hours;
      }
      var liHTML = "<div class='eligible-name'>" + name + "</div>" +
                   "<div title='" + desired_hours_title + "' class='eligible-hours'>" + curr_hours + "</div>"
      $li.html(liHTML);
    }
    
    // If employee assigned to schedule add highlight class to appropriate li
    _highlightAssignedEmployee(currAssignedEmployeeID);
  }
  
  /** Comparator function for sorting employees by last name, then first name */
  function compareEmployeeName(e1, e2) {
    e1Name = e1['employee'].last_name.toLowerCase() + e1['employee'].first_name.toLowerCase()
    e2Name = e2['employee'].last_name.toLowerCase() + e2['employee'].first_name.toLowerCase()
    
    return e1Name > e2Name
  }
  
  
  /** Given availability object, compile all conflict flags */
  function _compileConflictFlags(availability) {
    var warningFlagList = [];
    
    if (availability['(S)'].length > 0) {
      warningFlagList.push("S");
    }
    if (availability['(V)'].length > 0) {
      warningFlagList.push("V");
    }
    if (availability['(A)'].length > 0) {
      warningFlagList.push("U");
    }
    if (availability['(U)'].length > 0) {
      warningFlagList.push("U-Re");
    }
    if (availability['(O)']) {
      warningFlagList.push("O");
    }
    if (warningFlagList.length > 0) {
      var warningFlag = "(";
      
      for (i = 0; i < warningFlagList.length - 1; i++) {
        warningFlag += warningFlagList[i] + ", ";
      }
      warningFlag = warningFlag + warningFlagList[warningFlagList.length-1] + ")";
      return warningFlag;
    } else {
      return "";
    }
  }
  
  
  /** Given availability object, compile all conflicts into readable string. */
  function _compileConflictWarnings(availability) {
    var warningStr = "";
    
    if (availability['(S)'].length > 0) {
      warningStr += "<h4>Schedules That Overlap:</h4>";
      for (schedule of availability['(S)']) {
        var str = _scheduleConflictToStr(schedule);
        warningStr += "<p>" + str + "</p>";
      }
    }
    if (availability['(V)'].length > 0) {
      warningStr += "<h4>Vacations That Overlap:</h4>";
      for (vacation of availability['(V)']) {
        var str = _timeOffConflictToStr(vacation);
        warningStr += "<p>" + str + "</p>";
      }
    }
    if (availability['(A)'].length > 0) {
      warningStr += "<h4>Unavailabilities That Overlap:</h4>";
      for (absences of availability['(A)']) {
        var str = _timeOffConflictToStr(absences);
        warningStr += "<p>" + str + "</p>";
      }
    }
    if (availability['(U)'].length > 0) {
      warningStr += "<h4>Repeating Unavailabilities That Overlap:</h4>";
      for (repeat_unav of availability['(U)']) {
        var str = _repeatUnavConflictToStr(repeat_unav);
        warningStr += "<p>" + str + "</p>";
      }
    }
    if (availability['(O)']) {
      warningStr += "<h4>Assignment Will Put Employee In Overtime:</h4>";
      warningStr += "<p>" + "Employee Will Be Working " 
      warningStr += availability['Hours Scheduled']
      warningStr += " Hours This Workweek If Assigned." + "</p>";
    }
    return warningStr;
  }
  
  
  /** Create string of classes that color an eligable li according to availability. */
  function _compileColorClasses(employee, availability) {
    var classes = "";
    
    // Select background color of eligible li corresponding to availability
    if ((availability['(S)'].length > 0) || (availability['(V)'].length > 0) || 
        (availability['(A)'].length > 0) || (availability['(U)'].length > 0)) {
      classes += "red-bg-eligible";
    } else if (availability['(O)'] || (availability['Hours Scheduled'] >
                                       employee['desired_hours'] + displaySettings["desired_hours_overshoot_alert"])) {
      classes += "orange-bg-eligible";
    } else if (availability['Desired Times'].length > 0) {
      classes += "green-bg-eligible"
    }
    
    return classes;
  }
  
  
  /** Helper function to translate a schedule into warning string. */ 
  function _scheduleConflictToStr(schedule) {
    var str = $("#id_department > option:nth-child("+schedule.department+")").text();
    str += " Department"
    
    var startDate = moment(schedule.start_datetime);
    str += startStr = startDate.format(" on MMMM Do, YYYY: ");
    
    time_and_employee = getEventStr(schedule.start_datetime, schedule.end_datetime, 
                                    false, false, null, null);              
    str += time_and_employee;
    return str
  }
  
  
  /** Helper function to translate a vacation or absence into warning string. */ 
  function _timeOffConflictToStr(time_off) {
    var startDate = moment(time_off.start_datetime);
    var str = startDate.format("MMMM Do, YYYY to ");

    var endDate = moment(time_off.end_datetime);
    str += endDate.format("MMMM Do, YYYY");

    return str
  }
  
  
  /** Helper function to repeating unavailability into warning string. */ 
  function _repeatUnavConflictToStr(repeat_unav) {
    var str = WEEKDAYS[repeat_unav.weekday] + "s from "
    
    TIME_FORMAT = "HH:mm:ss"
    var startTime = moment(repeat_unav.start_time, TIME_FORMAT);
    str += startTime.format("h:mm to ");

    var endTime = moment(repeat_unav.end_time, TIME_FORMAT);
    str += endTime.format("h:mm");

    return str
  }
  
  
  /** Clear out eligable list and hide the schedule info section */
  function clearEligables() {
    $eligableList.empty();
    $scheduleInfo.css("display", "none");
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
   * Given an employee id and schedule length, add hours to newly selected
   * employee, and if previously selected different employee, subtract hours
   */ 
  function _updateCurrHours(employeeID, scheduleLength) {
    var $newlyAssignedEmployee = $("#" + employeeID + " .eligible-hours");
    var oldHours = $newlyAssignedEmployee.text();
    var newHours = parseFloat(oldHours) + scheduleLength;
    $newlyAssignedEmployee.text(newHours);
    var $previousAssignedEmployee = $(".curr-assigned-employee");
    if ($previousAssignedEmployee.length) {
      var $PreviousEmployeeHours = $previousAssignedEmployee.children(" .eligible-hours");
      var oldHours = $PreviousEmployeeHours.text();
      var newHours = parseFloat(oldHours) - scheduleLength;
      $PreviousEmployeeHours.text(newHours);
    }
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
      var calendarDate = $("#add-date").val();
      $.post("add_employee_to_schedule",
             {employee_pk: empPk, schedule_pk: schPk, cal_date: calendarDate},
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
    var calendarDate = $("#add-date").val();
    $.post("add_employee_to_schedule",
           {employee_pk: empPk, schedule_pk: schPk, cal_date: calendarDate},
           updateScheduleView);
  }
    

  /**
   * Given a successful HTTP response update event string to reflect newly
   * assigned employee.
   */
  function updateScheduleView(data) {
    var info = JSON.parse(data);
    var schedulePk = info["schedule"]["id"];
    var schEmployeePk = info["schedule"]["employee"];
    var startDateTime = info["schedule"]["start_datetime"]; 
    var endDateTime = info["schedule"]["end_datetime"];
    var hideStart = info["schedule"]["hide_start_time"];
    var hideEnd = info["schedule"]["hide_end_time"];
    var note = info["schedule"]["schedule_note"];
    var firstName = info["employee"]["first_name"];
    var lastName = info["employee"]["last_name"];
    var str = getEventStr(startDateTime, endDateTime,
                          hideStart, hideEnd,
                          firstName, lastName,
                          note);
    // Add employee to name dictionary if not already in dict                   
    if (!employeeNameDict.hasOwnProperty(schEmployeePk)) {
      employeeNameDict[schEmployeePk] = {"firstName": firstName,
                                         "lastName": lastName};
    }
    // Update the select eligible employee highlight and also update hours 
    // worked by new employee, and previous assigned employee (if applicable).
    var start = moment(startDateTime);
    var date = start.format(DATE_FORMAT);
    var end = moment(endDateTime);
    var duration = moment.duration(end.diff(start));
    var hours = duration.asHours();
    _updateCurrHours(info["employee"]["id"], hours);
    _highlightAssignedEmployee(info["employee"]["id"]);
    $event = $fullCal.fullCalendar("clientEvents", schedulePk);
    if (displaySettings["unique_row_per_employee"]) {
      var oldEventRow = $event[0].eventRowSort;
      var newEventRow = employeeRowList.indexOf(schEmployeePk);
      if (newEventRow == -1) { // Employee has never been assigned this month
        employeeRowList.push(schEmployeePk);
        newEventRow = employeeRowList.length - 1;
        //Check if old employee unassaigned
        _createBlankEventsForNewRow(newEventRow, schEmployeePk, date);
      }
      $event[0].eventRowSort = newEventRow;
      // Create/delete blank schedules to keep row order
      if (oldEventRow != EMPLOYEELESS_EVENT_ROW) {
        var eventRowEmployeePk = employeeRowList[oldEventRow];
        var fullCalEvent = _createBlankEvent(date, eventRowEmployeePk, oldEventRow);
        $fullCal.fullCalendar('renderEvent', fullCalEvent);
      }
      // If blank event exists, query it from fullcalendar and delete it
      var blankId = date + "-" + schEmployeePk;
      $fullCal.fullCalendar('removeEvents', blankId);
    }
    $event[0].title = str;
    $event[0].employeePk = schEmployeePk;
    $event[0].employeeAssigned = true;
    $fullCal.fullCalendar("updateEvent", $event[0]);
    // Click newly updated event
    var $event_div = $("#event-id-" + $event[0].id).find(".fc-content");
    $event_div.addClass("fc-event-clicked"); 
    // Update cost display to reflect any cost changes
    addCostChange(info["cost_delta"]);
  }
  
  
  /** Helper function that creates blank events for each date for row */ 
  function _createBlankEventsForNewRow(newEventRow, eventRowEmployeePk, date) {
    // TO DO: 
    // 1) Collect all dates that have events
    // 2) For each date (except given date), create blank event with row for employee
    // 3) Render events
    console.log("We got here")
    var fullCalEvents = $fullCal.fullCalendar("clientEvents");
    var datesWithEvents = [];
    var blankEvents = [];
    for (var i=0; i<fullCalEvents.length; i++) {
      var start = moment(fullCalEvents[i].start);
      var eventDate = start.format(DATE_FORMAT);
      if (date != eventDate && fullCalEvents[i].isSchedule && !datesWithEvents.includes(eventDate)) {
        datesWithEvents.push(eventDate);
      }
    }
    console.log("create blank events for new row dates are: ");
    console.log(datesWithEvents);
    for (var i=0; i<datesWithEvents.length; i++) {
      var blankEvent = _createBlankEvent(datesWithEvents[i], eventRowEmployeePk, newEventRow);
      blankEvents.push(blankEvent);
    }
    $fullCal.fullCalendar("renderEvents", blankEvents);  
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
                          null, null);
    var eventRow = 1;
    if (displaySettings["unique_row_per_employee"]) { 
      eventRow = EMPLOYEELESS_EVENT_ROW 
      // If no blank events exist for day without events, create them
      var start = moment(startDateTime);
      var date = start.format(DATE_FORMAT);
      var eventsExistForDate = _checkIfAnyEventsOnDate(date);
      if (!eventsExistForDate) {
        blankEvents = [];
        for (var i=0; i<employeeRowList.length; i++) {
          var eventRowEmployeePk = employeeRowList[i];
          var fullCalEvent = _createBlankEvent(date, eventRowEmployeePk, i);
          blankEvents.push(fullCalEvent);
        }
        $fullCal.fullCalendar("renderEvents", blankEvents);   
      }
    }
    var event = {
      id: schedulePk,
      title: str,
      start: startDateTime,
      end: endDateTime,
      allDay: true,
      isSchedule: true,
      isNote: false,
      employeeAssigned: false,
      customSort: 0,
      eventRowSort: eventRow,
      employeePk: -1
    }
    $fullCal.fullCalendar("renderEvent", event);
    //Highlight newly created event
    $(".fc-event-clicked").removeClass("fc-event-clicked");
    var $event_div = $("#event-id-" + schedulePk).find(".fc-content");
    $event_div.addClass("fc-event-clicked"); 
    // Update schedule note form field
    $scheduleNoteText.val("");
    $scheduleNoteBtn.prop('disabled', false);
    // Get eligables for this new schedule
    $.get("get_schedule_info", {pk: schedulePk}, displayEligables);
  }
  
  
  /** Helper function that returns boolean if any events for a date exist */ 
  function _checkIfAnyEventsOnDate(date) {
    var fullCalEvents = $fullCal.fullCalendar("clientEvents");
    for (var i=0; i<fullCalEvents.length; i++) {
      var start = moment(fullCalEvents[i].start);
      var eventDate = start.format(DATE_FORMAT);
      if (date == eventDate && !fullCalEvents[i].isNote) { return true; }
    }
    return false;
  }
  

  /** Give user warning dialog to choose if they want to remove schedule. */
  function removeSchedule() {
    $removeScheduleBtn.css("display", "none");
    $removeBtnConfirmContainer.css("display", "block");
  }
  
  
  /** Remove selected schedule after user has clicked okay on warning dialog. */
  function _removeScheduleAfterWarning(event) {
    var event_id = $(".fc-event-clicked").parent().data("event-id");
    var calendarDate = $("#add-date").val();
    if (event_id) {
      $.post("remove_schedule", 
             {schedule_pk: event_id, cal_date: calendarDate}, 
             removeEventAfterDelete);
    }
  }
    
    
  /**
   * Given successful response for deleting schedule, remove corresponding
   * event from fullCalendar.
   */
  function removeEventAfterDelete(data) {
    var info = JSON.parse(data);
    $removeScheduleBtn.css("display", "block");
    $removeBtnConfirmContainer.css("display", "none");
    var schedulePk = info["schedule_pk"];
    // Update title string to reflect changes to schedule & rehighlight
    $event = $fullCal.fullCalendar("clientEvents", schedulePk);
    if (!displaySettings["unique_row_per_employee"] || $event[0].eventRowSort == EMPLOYEELESS_EVENT_ROW) {
      $fullCal.fullCalendar("removeEvents", schedulePk);
    } else {
      var start = moment($event[0].start);
      var date = start.format(DATE_FORMAT);
      var eventRow = $event[0].eventRowSort;
      var employeePk = employeeRowList[eventRow];
      // Check if employee is assigned more than once per day, if not, create 
      // a blank event to maintain row sort integrity
      if (!_employeeAssignedMoreThanOnceOnDate(date, employeePk)) {
        var blankEvent = _createBlankEvent(date, employeePk, eventRow);
        $fullCal.fullCalendar("renderEvent", blankEvent);
      }
      $fullCal.fullCalendar("removeEvents", schedulePk);
    }
    // Clear out eligable list
    $eligableList.empty();
    $scheduleInfo.css("display", "none");
    // Update cost display to reflect any cost changes
    addCostChange(info["cost_delta"]);
    // Disable schedule note
    $scheduleNoteText.val("Please Select A Schedule First");
    $scheduleNoteBtn.prop('disabled', true);
  }
  
    
  /** Change times and hide start/end booleans */
  function editSchedule(event) {
    var event_id = $(".fc-event-clicked").parent().data("event-id");
    var startTime = $("#start-timepicker").val();
    var endTime = $("#end-timepicker").val();
    var hideStart = $("#start-checkbox").prop('checked');
    var hideEnd = $("#end-checkbox").prop('checked');
    
    console.log(startTime);
    console.log(endTime);
    console.log(hideStart);
    console.log(hideEnd);
    
    if (event_id) {
      $.post("edit_schedule", 
             {schedule_pk: event_id, start_time: startTime, end_time: endTime,
              hide_start: hideStart, hide_end: hideEnd}, 
             successfulScheduleEdit);
    }
  }
  
  
  /** Update schedule string and cost */
  function successfulScheduleEdit(data) {
    var info = JSON.parse(data);
    var schedule = info["schedule"];
    var schedulePk = schedule["id"];
    var startDateTime = schedule["start_datetime"]; 
    var endDateTime = schedule["end_datetime"];
    var hideStart = schedule["hide_start_time"];
    var hideEnd = schedule["hide_end_time"];
    var employeePk = schedule["employee"];
    var firstName = "";
    var lastName = "";
    if (employeePk != null) {
      var firstName = employeeNameDict[employeePk]["firstName"];
      var lastName = employeeNameDict[employeePk]["lastName"];
    }
    var note = schedule["schedule_note"];
    var str = getEventStr(startDateTime, endDateTime,
                          hideStart, hideEnd,
                          firstName, lastName, 
                          note);
    // Update title string to reflect changes to schedule & rehighlight
    $event = $fullCal.fullCalendar("clientEvents", schedulePk);
    
    //
    // Somewhere here lets edit the hours...
    //
    
    $event[0].title = str;
    $fullCal.fullCalendar("updateEvent", $event[0]);
    
    //Highlight newly created event
    var $event_div = $("#event-id-" + schedulePk).find(".fc-content");
    $event_div.addClass("fc-event-clicked"); 
    
    //TODO: Add in cost change.
  }
  
  /** Helper function that returns true if employee assigned more than once on date */ 
  function _employeeAssignedMoreThanOnceOnDate(date, employeePk) {
    var fullCalEvents = $fullCal.fullCalendar("clientEvents");
    var assignmentCount = 0;
    for (var i=0; i<fullCalEvents.length; i++) {
      var start = moment(fullCalEvents[i].start);
      var eventDate = start.format(DATE_FORMAT);
      if (date == eventDate && fullCalEvents[i].employeePk == employeePk) { 
        assignmentCount += 1;
      }
    }
    if (assignmentCount > 1) {
      return true;
    } else {
      return false;
    }
  }
  
  
  /** Helper function removes employee from row & blank events if the employee
      is no longer assigned to any schedules for the current selected month */ 
  function _removeEmployeeFromRow(employeePk, eventRow) {
    var fullCalEvents = $fullCal.fullCalendar("clientEvents");
    var blankEventsWithSameRowNumber = [];
    for (var i=0; i<fullCalEvents.length; i++) {
      if (fullCalEvents[i].eventRowSort == eventRow) {
        if (fullCalEvents[i].employeeAssigned) { return; }
        blankEventsWithSameRowNumber.push(fullCalEvents[i]);
      }
    }
    for (var i=0; i<blankEventsWithSameRowNumber.length; i++) {
      var blankEventId = blankEventsWithSameRowNumber[i].id
      $fullCal.fullCalendar("removeEvents", blankEventId);
    }
    employeeRowList.splice(eventRow, 1);
  }

  
  /** Callback function to show user the eligible legend */
  function showEligibleLegend(event) {
    $legendModal = $("#legendModal");
    $legendModal.css("margin-top", Math.max(0, ($(window).height() - $legendModal.height()) / 2));
    $legendModal.modal('show');
  }
  
  
  /** Callback function to show user the date note modal */
  function showDayNoteModal(event) {
    $prev_day_clicked = $(".fc-day-clicked"); // Check if a date has been clicked
    if ($prev_day_clicked.length) {
      $dayNoteModal = $("#noteModal");
      $dayNoteModal.css("margin-top", Math.max(0, ($(window).height() - $dayNoteModal.height()) / 2));
      $dayNoteModal.modal('show');
    } else {
      $alertDayNoteModal = $("#noteAlertModal");
      $alertDayNoteModal.css("margin-top", Math.max(0, ($(window).height() - $alertDayNoteModal.height()) / 2));
      $alertDayNoteModal.modal('show');
    }
  }
  
  
  /** Callback to push changes to date's header note to database */
  function postDayNoteHeader(event) {
    var text_val = $dayNoteHeaderText.val();
    $.post("add_edit_day_note_header",
           {date: $addScheduleDate.val(), header_text: text_val, department: calDepartment},
            _updateDayNoteHeader);
  }
  
  
  /** Callback function to update the current selected date's header note */
  function _updateDayNoteHeader(dayNoteHeaderJSON) {
    var dayNoteHeader = JSON.parse(dayNoteHeaderJSON);
    dayNoteHeaders[dayNoteHeader["date"]] = dayNoteHeader;
    _dayNoteHeaderRender(dayNoteHeader);
  }
  

  /** Callback to push changes to date's body note to database */
  function postDayNoteBody(event) {
    var text_val = $dayNoteBodyText.val();
    $.post("add_edit_day_note_body",
           {date: $addScheduleDate.val(), body_text: text_val, department: calDepartment},
            _updateDayNoteBody);
  }
  
  
  /** Callback function to update the current selected date's body note */
  function _updateDayNoteBody(dayNoteBodyJSON) {
    var dayNoteBody = JSON.parse(dayNoteBodyJSON);
    var eventID = "body-note-" + dayNoteBody["date"];
    var $selectedScheduleEvent = $(".fc-event-clicked").parent();
    // Update body note if it already exists or create new event if not
    if (dayNoteBodies.hasOwnProperty(dayNoteBody["date"])) {
      $event = $fullCal.fullCalendar("clientEvents", eventID);
      $event[0].title = dayNoteBody["body_text"];
      // Update then rehighlight edited schedule
      $fullCal.fullCalendar("updateEvent", $event[0]);
    } else {
        var event = {
          id: eventID,
          title: dayNoteBody["body_text"],
          start: dayNoteBody["date"],
          allDay: true,
          isSchedule: false,
          isNote: true,
          customSort: 1,
          eventRowSort: 2000,
          className: "blank-event"
        }
        $fullCal.fullCalendar("renderEvent", event);
    }
    dayNoteBodies[dayNoteBody["date"]] = dayNoteBody;
    
    // If schedule was previously clicked, rehighlight it
    if ($selectedScheduleEvent.length > 0) {
      var selectedScheduleEventID = $selectedScheduleEvent.attr('id');
      var $event_div = $("#" + selectedScheduleEventID).find(".fc-content");
      $event_div.addClass("fc-event-clicked");
    }
  }
  
  /** Callback to push changes to date's body note to database */
  function postScheduleNote(event) {
    var schedule_pk = $(".fc-event-clicked").parent().data("event-id");
    var text_val = $scheduleNoteText.val();
    $.post("edit_schedule_note",
           {schedule_pk: schedule_pk, schedule_text: text_val},
            _updateScheduleNote);
  }
  
  
  /** Callback function to update the current selected schedule's note */
  function _updateScheduleNote(scheduleJSON) {
    var schedule = JSON.parse(scheduleJSON);
    var schedulePk = schedule["id"];
    var startDateTime = schedule["start_datetime"]; 
    var endDateTime = schedule["end_datetime"];
    var hideStart = schedule["hide_start_time"];
    var hideEnd = schedule["hide_end_time"];
    var employeePk = schedule["employee"];
    var firstName = "";
    var lastName = "";
    if (employeePk != null) {
      var firstName = employeeNameDict[employeePk]["firstName"];
      var lastName = employeeNameDict[employeePk]["lastName"];
    }
    var note = schedule["schedule_note"];
    var str = getEventStr(startDateTime, endDateTime,
                          hideStart, hideEnd,
                          firstName, lastName, 
                          note);
    // Update title string to reflect changes to schedule & rehighlight
    $event = $fullCal.fullCalendar("clientEvents", schedulePk);
    $event[0].title = str;
    $fullCal.fullCalendar("updateEvent", $event[0]);
    var $event_div = $("#event-id-" + schedulePk).find(".fc-content");
    $event_div.addClass("fc-event-clicked"); 
    // Update the collection of schedule notes for updating form text field
    scheduleNotes[schedulePk] = note;
  }
  
  
  /** Clear eligibles */
  function clearEligables() {
    $eligableList.empty();
    $scheduleInfo.css("display", "none");
  }
  
  
  /** Callback function to show user the employeeless modal */
  function _showEmployeelessModal() {
    $employeelessModal = $("#employeelessModal");
    $employeelessModal.css("margin-top", Math.max(0, ($(window).height() - $employeelessModal.height()) / 2));
    $employeelessModal.modal('show');
  }
  
  /** Callback function to show user the employeeless department modal. This is 
   *  called when employees do exist for the user, but none are members of the
   *  department of the calendar the user is currently editing.
   */
  function _showEmployeelessDepartmentModal() {
    $employeelessDepartmentModal = $("#employeelessDepartmentModal");
    $employeelessDepartmentModal.css("margin-top", Math.max(0, ($(window).height() - $employeelessDepartmentModal.height()) / 2));
    $employeelessDepartmentModal.modal('show');
  }
  
  
  /** Callback function load schedule pks into array to create copies later */
  function copySchedulePks() {
    $prev_day_clicked = $(".fc-day-clicked"); // Check if a date has been clicked
    if ($prev_day_clicked.length) {
      var date = $addScheduleDate.val();
      var schedulePks = [];
      var fullCalEvents = $fullCal.fullCalendar("clientEvents");
      for (var i=0; i<fullCalEvents.length; i++) {
        var start = moment(fullCalEvents[i].start);
        var eventDate = start.format(DATE_FORMAT);
        if (date == eventDate && fullCalEvents[i].isSchedule) {
          schedulePks.push(fullCalEvents[i].id);
        }
      }
      copySchedulePksList = schedulePks;
    } else {
      $alertDayNoteModal = $("#noteAlertModal");
      $alertDayNoteModal.css("margin-top", Math.max(0, ($(window).height() - $alertDayNoteModal.height()) / 2));
      $alertDayNoteModal.modal('show');
    }
  }
  
  
  /** Helper function to send post request to server to copy schedules */
  function dblClickHelper() {
    if (copySchedulePksList.length) {
      $.post("copy_schedules",
             {date: $addScheduleDate.val(), schedule_pks: copySchedulePksList},
             _createCopySchedules);
    }
  }
  
  
  /** Callback function to render copied schedules */
  function _createCopySchedules(data) {
    console.log(data);
    var info = JSON.parse(data);
    var schedules = info["schedules"];
    // Create fullcalendar events corresponding to schedules
    if (displaySettings["unique_row_per_employee"]) {
      var events = _schedulesToUniqueRowEvents(schedules, employeeNameDict);
    } else {
      var events = _schedulesToEvents(schedules, employeeNameDict);
    }
    // Render event collection
    $fullCal.fullCalendar("renderEvents", events);
  }
  
  
  /** Add/Remove class to toolbar to make it fixed/static on scroll */
  function stickyToolbar() {
    if (window.pageYOffset >= sticky) {
      toolbar.classList.add("sticky");
    } else {
      toolbar.classList.remove("sticky");
    }
  }
  
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