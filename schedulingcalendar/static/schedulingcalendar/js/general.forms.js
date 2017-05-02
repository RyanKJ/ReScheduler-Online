$(function(){
    // Connect each employee-li to javascript callback
    //$('.list-group li').click(highlightEmployeeLi);

    
    /** Highlight employee li if successfully loaded. */ 
    //function highlightEmployeeLi(event) {
    //    $employee_li = $(this);
    //    $employee_li.parent().find('li').removeClass('active');
    //    $employee_li.addClass('active');
    //}
    
    
    // Create start and end time-pickers for adding schedules
    //var $startTimePicker = $("#id_start_datetime").pickadate();
    //var $endTimePicker = $("#id_end_datetime").pickadate();
      
    // Set default start and end time for time-pickers
    //var st_picker = $startTimePicker.pickatime("picker");
    //st_picker.set("select", [8,0]);
    //var et_picker = $endTimePicker.pickatime("picker");
    //et_picker.set("select", [17,0]);
    
    
  //Pickadate does not support single datetime picker, so customized 
  //date and time pickers are created so that a time picker is focused
  //after a date is picked, which is then combined and added into the input
  //text field.
  //Code found from: https://github.com/amsul/pickadate.js/issues/267
    
  var startDatepicker = $('#hidden-start-date').pickadate({
    container: '#outlet',
    onSet: function(item) {
            if ( 'select' in item ) setTimeout( startTimepicker.open, 0 )
           }
    }).pickadate('picker')

  var startTimepicker = $('#hidden-start-time').pickatime({
    container: '#outlet',
    onRender: function() {
      $('<button>back to date</button>').
        on('click', function() {
          startTimepicker.close()
            startDatepicker.open()
        }).prependTo( this.$root.find('.picker__box') )
    },
    onSet: function(item) {
      if ( 'select' in item ) setTimeout( function() {
        $start_datetime.
        off('focus').
        val( startDatepicker.get() + ' at ' + startTimepicker.get() ).
          focus().
            on('focus', startDatepicker.open)
      }, 0 )
    }
  }).pickatime('picker')
  
  
  var endDatepicker = $('#hidden-end-date').pickadate({
    container: '#outlet',
    onSet: function(item) {
            if ( 'select' in item ) setTimeout( endTimepicker.open, 0 )
           }
    }).pickadate('picker')

  var endTimepicker = $('#hidden-end-time').pickatime({
    container: '#outlet',
    onRender: function() {
      $('<button>back to date</button>').
        on('click', function() {
          endTimepicker.close()
            endDatepicker.open()
        }).prependTo( this.$root.find('.picker__box') )
    },
    onSet: function(item) {
      if ( 'select' in item ) setTimeout( function() {
        $end_datetime.
        off('focus').
        val( endDatepicker.get() + ' at ' + endTimepicker.get() ).
          focus().
            on('focus', endDatepicker.open)
      }, 0 )
    }
  }).pickatime('picker')
  

  var $start_datetime = $('#id_start_datetime').
      on('focus', startDatepicker.open).
      on('click', function(event) { event.stopPropagation(); startDatepicker.open() })
      
  var $end_datetime = $('#id_end_datetime').
      on('focus', endDatepicker.open).
      on('click', function(event) { event.stopPropagation(); endDatepicker.open() })
})