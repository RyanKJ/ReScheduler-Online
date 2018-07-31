$(function(){
  $.get("/check_pending_approvals", {}, renderPendingApprovalsNavBtn);
  
  
  /** Get root hostname */
  function getRootHostName() {
    var pathArray = window.location.host.split( '/' );
    return window.location.protocol + "//" + pathArray[0];
  }
  
  
  /** Render a navigation button to pending approvals if any exist. */
  function renderPendingApprovalsNavBtn(data) {
    var info = JSON.parse(data);
    var hostName = getRootHostName();
    
    if (info["pending_applications"]) {
      var html = "<li class='nav-item custom-nav-item active pending-btn'><a class='nav-link' href='"
      html += hostName + "/pending_approvals/'>Pending Approvals</a></li>"
      
      $("#header-nav").prepend(html);
    }
  }
});