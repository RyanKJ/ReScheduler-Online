$(function(){
  // Create start and end time-pickers
  $("#id_start_time").pickatime({
    format: 'hh:i A'
  });
  $("#id_end_time").pickatime({
    format: 'hh:i A'
  });
})