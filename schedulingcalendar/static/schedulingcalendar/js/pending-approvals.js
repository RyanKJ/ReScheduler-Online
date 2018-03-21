

$(document).ready(function() {
  /**
   * Selectors And Variables
   */
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
    // 1) Find li with id
    // 2) Remove li
    alert("Success!");  
  }
  
}); 