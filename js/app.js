
$(document).ready(function() {
	/* Troop page functions */
	if ($('#page-troop').length > 0) {
		var maintable = $('#maintable');
			maintable.dataTable({
			scrollX:true,
			scrollY:true,
			paging:false,
			ordering:false,
			info:false,
			fixedColumns:true,
			fixedHeader:false, // doesn't work with scrolling
			searching:false,
			bScrollCollapse:true,
			bScrollAutoCss:true,
			bAutoWidth:true
			//responsive:true
	    });
	
		setTimeout(function (){
			// hack/fix for webkit to match sizes after css has been applied
			maintable.fnAdjustColumnSizing();
		}, 10);

	    // Update count on all buttons
		var btns = $('.postattendance');
	
		for (var i=0; i < btns.length; i++) {
			var meeting_url = btns[i].id.slice(3); // "btn..."
			updateParticipantCount(meeting_url);
		}	// end
		
		var DIRTY_COLOR = '#fa0';
		var timerID = 0;
		
		var delay = (function() {
			return function(callback, ms) {
				clearTimeout(timerID);
				timerID = setTimeout(callback, ms);
			};
		})();

		$(window).on('beforeunload', function(e) {
			if (!isDirty()) {
				return undefined;
			}

			var confirmationMessage = 'Du har osparade ändringar.';
			return confirmationMessage; //Gecko + Webkit, Safari, Chrome etc.
		});

		$('.togglebutton').click(function(event) {
			// hack because shown.bs.collapse doesn't trigger with datatable included
			setTimeout(function() {
				$(event.target.attributes['set-focus'].value)[0].focus();
			}, 200);
		});

		// page-troop event handlers
		$('.attendance-cb').click(function(event) {
			meeting_url = event.target.name.slice(2);
			var btn = $('#btn'+meeting_url);
		
			btn.css('background-color',DIRTY_COLOR);
			btn.attr('data-dirty','1');
		
			updateParticipantCount(meeting_url);
			$(".saveinfo").text("Klicka för att spara:");
		});

		$('#namesearch').on('keyup', function() {
			var val = $('#namesearch').val();

			if (val && val.length > 1) {
				delay($.ajax({
					url: '.',
					type: 'GET',
					data: 'action=lookupperson&name=' + val,
					async: true,
					success: function(data, textStatus, jqXHR) {
						arr = JSON.parse(data);
						t = '';
						
						$('#tblSearchResults').remove();
						table = $('<table id="tblSearchResults" class="table table-striped"/>');
						
						for (var x in arr) {
							table.append($('<tr><td><a href="' + arr[x].url + '?action=addperson"> + ' + arr[x].name + '</a></td></tr>'));
						}

						$('#nameResults').append(table);
						return data;
					}
				}), 1000);
			} else {
				clearTimeout(timerID);
				$('#tblSearchResults').remove();
			}
		});

	} // End page-troop

	/* Main page function s*/ 
	if ($('#page-main').length > 0) {
		
		$(".attendance-cb").click(function(event) {
			meeting_url = event.target.name.slice(2);
			$('#btn'+meeting_url).css('background-color','#fa0');
		});
		
		$("#namesearch").on("keyup", function() {
			var val = $("#namesearch").val();
		
			if (val && val.length > 1) {
				$.ajax({
					url: '.',
					type: 'GET',
					data: 'action=lookupperson&name=' + val,
					async: true,
					success: function(data, textStatus, jqXHR) {
						arr = JSON.parse(data);
						t = "";
						$("#tblSearchResults").remove();
						table = $('<table id="tblSearchResults" class="table table-striped"/>');
						
						for (var x in arr) {
							table.append($('<tr><td><a href="' + arr[x].url + '?action=addperson">' + arr[x].name + '</a></td></tr>'));
						}
						$("#nameResults").append(table);
						
						return data;
					}
				});
			} else {
				$("#tblSearchResults").remove();
			}
		});
	
	} // End page-main

	/***
	 * Common event handlers
 	 ***/ 
 	 $('input.groupaccess').on('change', function(e) {
 	 	var check = $(this).attr('checked');
 	 	var url = '#';

 	 	if (check === undefined) {
 	 		$(this).attr('checked', 'checked');
 	 		url = $(this).data('add-url');
 	 	} else {
 	 		$(this).removeAttr('checked');
 	 		url = $(this).data('remove-url');
 	 	}

 	 	$.get(url, function(data) {
 	 		// nothing here... 
 	 	});
 	 });

	$("#newmeeting").on('shown.bs.collapse', function(e) {
		$("#mname")[0].focus();
	});

	$("#newmember").on('shown.bs.collapse', function(e) {
		$("#namesearch")[0].focus();
	});

	$(".postattendance").click(function(event) {
		var button = event.target;

		if (button.type != "button") // if you press on the glyphicon inside the button
			button = event.target.parentNode; // get the parent button instead
			
		var meeting_url = button.id.slice(3);
		var checkboxes = $('input:checkbox[name="cb' + meeting_url + '"]');

		persons = '';

		for (var cb=0; cb < checkboxes.length; cb++) {
			if (persons.length > 0) persons += ',';
			
			if (checkboxes[cb].checked) {
				persons += checkboxes[cb].id;
			}
		}
		
		var fd = new FormData();
		fd.append("action", "saveattendance");
		fd.append("persons", persons);
		
		$('#btn'+meeting_url).css('background-color','#FFFF00');
		
		$.ajax({
			url:'./'+meeting_url+"/",
			data: fd,
			processData: false,
			contentType: false,
			type: 'POST',
			success: function(data) { if (data === "ok") $('#btn'+meeting_url).css('background-color','#00FF00');}
		});
	});

}); // End onready

/***
 * Common Functions
 ***/ 
function isDirty()
{
	var dd = $('.postattendance').attr('data-dirty');

	if (!dd) {
		return false;
	} else if (dd == '1') {
		return true;
	}
	
	return false;
}

function getTodaysDateString()
{
	var today = new Date();
	var dd = ("0" + (today.getDate())).slice(-2);
	var mm = ("0" + (today.getMonth() + 1)).slice(-2);
	var yyyy = today.getFullYear();

	today = yyyy + '-' + mm + '-' + dd ;

	return today;
}

function getCurrentHalfHourString()
{
	var today = new Date();
	var h = today.getHours();
	var m = today.getMinutes();
	var frac = Math.round(m/60*2.0)/2.0;

	m = (frac * 60) % 60;

	if (frac > 0.5) {
		h += 1;
		h %= 24;
	}

	var hh = ("0" + h).slice(-2);
	var mm = ("0" + m).slice(-2);
	timestr = hh + ':' + mm;
	
	return timestr;
}

function postWithParams(path, params, method) 
{
	method = method || "post";
	var form = document.createElement("form");

	form.setAttribute("method", method);
	form.setAttribute("action", path);

	for(var key in params) {
		if (params.hasOwnProperty(key)) {
			var hiddenField = document.createElement("input");
			hiddenField.setAttribute("type", "hidden");
			hiddenField.setAttribute("name", key);
			hiddenField.setAttribute("value", params[key]);
			form.appendChild(hiddenField);
		 }
	}
	
	document.body.appendChild(form);
	form.submit();
}

function postData(absolutePath, data, onsuccess, onfailure)
{
	var XHR = new XMLHttpRequest();
	var urlEncodedData = "";
	var urlEncodedDataPairs = [];
	var name;

	// We turn the data object into an array of URL encoded key value pairs.
	for(name in data) {
		urlEncodedDataPairs.push(encodeURIComponent(name) + '=' + encodeURIComponent(data[name]));
	}

	// We combine the pairs into a single string and replace all encoded spaces to 
	// the plus character to match the behaviour of the web browser form submit.
	urlEncodedData = urlEncodedDataPairs.join('&').replace(/%20/g, '+');

	// We define what will happen if the data is successfully sent
	XHR.addEventListener('load', function(event) {
		if (onsuccess) onsuccess();
	});

	// We define what will happen in case of error
	XHR.addEventListener('error', function(event) {
		if (onfailure) onfailure();
	});

	// We setup our request
	XHR.open('POST', absolutePath);

	// We add the required HTTP header to handle a form data POST request
	XHR.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
	// XHR.setRequestHeader('Content-Length', urlEncodedData.length);

	// And finally, We send our data.
	XHR.send(urlEncodedData);
}	

function postCheckboxesWithName(path, name, onsuccess, onfailure)
{
	var elem = document.getElementsByName(name);
	var persons = [];
	
	for (var i=0; i < elem.length; i++) {
		if (elem[i].checked) {
			persons.push(elem[i].id);
		}
	}
	
	var absolutePath = window.location.href;
	var lastChar = absolutePath.substr(-1);
	
	if (lastChar !== '/') {
		absolutePath = absolutePath + '/';
	} else if (lastChar !== '?') {
		absolutePath = absolutePath.substr(absolutePath.length);
	}
	
	absolutePath = absolutePath + path;
	postData(absolutePath, {meeting:name.slice(2), persons:persons}, onsuccess, onfailure);
}

function updateParticipantCount(meeting_url)
{
	var leaders = 0;
	var scouts = 0;
	var name = 'cb' + meeting_url;
	var checkboxes = $('input:checkbox[name="' + name + '"]');

	for (var cb=0; cb < checkboxes.length; cb++) {
		if (checkboxes[cb].checked) {
			var person_id = checkboxes[cb].id;
			var x = $('#name' + person_id)[0];
			var dd = x.attributes['data-leader'];
			if (dd !== undefined) {
				var v=dd.value;
			
				if (v == '1') {
					leaders++;
					continue;
				}
			}
			scouts++;
		}
	}
	$('#span' + meeting_url).html('' + scouts + '/' + leaders);
}

function resetDirtyButton(btn)
{
	btn.css('background-color','#00FF00');
	btn.removeAttr('data-dirty');

	if (!isDirty()) { 
		$(".saveinfo").text("");
	}
}

function changeSemester(x)
{
	if (window.confirm("Vill du byta termin?")) {
		location.href = "?action=setsemester&semester=" + x.options[x.selectedIndex].value;
	}
}

