

$(document).ready(function() {
  $(".btn-vacation-approve").click(approveVacationApplication);
  $(".btn-vacation-disapprove").click(disapproveVacationApplication);
  $(".btn-absence-approve").click(approveAbsenceApplication);
  $(".btn-absence-disapprove").click(disapproveAbsenceApplication);
  $(".btn-repeat-unav-approve").click(approveRepeatUnavApplication);
  $(".btn-repeat-unav-disapprove").click(disapproveRepeatUnavApplication);
   
   
  function approveVacationApplication(event) {
    var pk = $(this).data("pk");
    $.post("approve_vacation_app",
           {pk: pk},
           removeVacationApp);
  }
  
  
  function disapproveVacationApplication(event) {
    var pk = $(this).data("pk");
    $.post("disapprove_vacation_app",
           {pk: pk},
           removeVacationApp);
  }
  
  
  function removeVacationApp(data) {
    var info = JSON.parse(data);
    var pk = info['pk'];
    $(".vacation-obj[data-pk='" + pk + "']").remove()
  }
  
  
  function approveAbsenceApplication(event) {
    var pk = $(this).data("pk");
    $.post("approve_absence_app",
           {pk: pk},
           removeAbsenceApp);
  }
  
  
  function disapproveAbsenceApplication(event) {
    var pk = $(this).data("pk");
    $.post("disapprove_absence_app",
           {pk: pk},
           removeAbsenceApp);
  }
  
  
  function removeAbsenceApp(data) {
    var info = JSON.parse(data);
    var pk = info['pk'];
    $(".absence-obj[data-pk='" + pk + "']").remove()
  }
  
  
  function approveRepeatUnavApplication(event) {
    var pk = $(this).data("pk");
    $.post("approve_repeat_unav_app",
           {pk: pk},
           removeRepeatUnavApp);
  }
  
  
  function disapproveRepeatUnavApplication(event) {
    var pk = $(this).data("pk");
    $.post("disapprove_repeat_unav_app",
           {pk: pk},
           removeRepeatUnavApp);
  }
  
  
  function removeRepeatUnavApp(data) {
    var info = JSON.parse(data);
    var pk = info['pk'];
    $(".repeat-unav-obj[data-pk='" + pk + "']").remove()
  }
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
  var $disapproveSchSwapLi = $(".disapprove-sch-swap");
  $disapproveSchSwapLi.click(showDisapprovalModal);
  
  var $disapproveSchSwapBtn = $("#disapprove-schedule-swap-btn");
  $disapproveSchSwapBtn.click(disapproveScheduleSwap);

  
  function showDisapprovalModal() {
    var schSwapId = $(this).parent().attr("data-sch-swap-id");
    $disapproveSchSwapBtn.data("data-sch-swap-id", schSwapId);
    console.log(schSwapId);
    
    $disapprovalModal = $("#disapproveModal");
    $disapprovalModal.css("margin-top", Math.max(0, ($(window).height() - $disapprovalModal.height()) / 2));
    $disapprovalModal.modal('show');
  }
   

  function disapproveScheduleSwap(event) {
    var schSwapId = $(this).data("data-sch-swap-id")
    $.post("schedule_swap_disapproval",
           {schedule_swap_pk: schSwapId},
            successfulSchSwapDisapproval);
  }
  
  
  function successfulSchSwapDisapproval(data) {
    // TODO: Create modal success alert
    var info = JSON.parse(data);
    
    schSwapId = info["sch_swap_id"];
    var schSwapLi = $("[data-sch-swap-id='" + schSwapId + "']").parent();
    schSwapLi.remove();
    
    alert(info["message"]);  
  }
}); 