$(function(){
  $.get("/check_pending_approvals", {}, renderPendingApprovalsNavBtn);
  
  /** Render a navigation button to pending approvals if any exist. */
  function renderPendingApprovalsNavBtn(data) {
    var info = JSON.parse(data);
    if (info["pending_applications"]) {
      var html = "<li class='nav-item custom-nav-item active pending-btn'><a class='nav-link' href='"
      html += window.location.host + "/pending_approvals/'>Pending Approvals</a></li>"
      
      $("#header-nav").prepend(html);
    }
  }
});