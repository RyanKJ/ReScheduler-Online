$(function(){
  // Create a month picker
  $("#id_month_year").datepicker( {
    format: "yyyy, MM",
    viewMode: "months", 
    minViewMode: "months"
  });
})