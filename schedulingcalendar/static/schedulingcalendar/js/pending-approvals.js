

$(document).ready(function() {
  $(".btn-vacation-approve").click(approveVacationApplication);
  $(".btn-vacation-disapprove").click(disapproveVacationApplication);
   
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