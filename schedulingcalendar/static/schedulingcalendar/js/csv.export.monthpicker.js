$(function(){
  // Create a month picker
  $("#id_month_year_start").datepicker( {
    format: "yyyy, MM",
    viewMode: "months", 
    minViewMode: "months"
  });
  
  $("#id_month_year_end").datepicker( {
    format: "yyyy, MM",
    viewMode: "months", 
    minViewMode: "months"
  });
})