function _actionToUrl( action ) {
	return action + '.action';
}

function executeAction( action, paramsJson ) {
	var url = _actionToUrl( action );
	
	//if ( paramsJson != null ) url += '?' + $H(paramsJson).toQueryString();
	if ( paramsJson != null ) {
		var payloadString = Object.entries(paramsJson).map(e => e.join('=')).join('&');
		url += '?' + payloadString;
	}

	location.href = url;
}

function fnAjaxSubmit() {
	var args = arguments; //Parameters
	var url = args[0];
	var frm = args[1];
	console.log(frm);
	console.log($(frm));
	var callbackFunction = args[2];
	var msg = args[3];
	var mask = args[4]!=null?args[4]:false;
	var errorCallbackFunction = args[5]!=null?args[5]:false;
	
	$(frm).ajaxSubmit({
		dataType: 'json'
		, url: url
		, success: function(data){
			if (msg == null) {
				if (data != null && data.message != null && data.message != undefined) {
					alert(data.message.trim()); //성공 메시지 처리
				}
			} else if (msg != "") {
				// 자바에서 올라오는 BusinessException을 먼저 체크한 후 사용자메세지를 체크한다.
				if (data != null && data.message != null && data.message != undefined) {
					alert(data.message.trim());
				} else{
					alert(msg.trim()); //사용자 메시지 처리
					if (errorCallbackFunction != null && errorCallbackFunction != undefined && errorCallbackFunction != false) {
						errorCallbackFunction(data); // User Function Call
					}
				}
			}
			
			if (callbackFunction != null && callbackFunction != undefined) {
				callbackFunction(data); //User Function Call
			}
		}
		, error: function(xhr, status, err) {
			var responseText = xhr.responseText;	
			responseText = responseText.replace('{', '').replace('}', '').replace(/[\"]/g,'');		
			responseText = responseText.substring(responseText.indexOf(':') + 1).trim();
			alert(responseText);
			
			if (errorCallbackFunction != null && errorCallbackFunction != undefined && errorCallbackFunction != false) {
				errorCallbackFunction(); // User Function Call
			}
		}
		, beforeSubmit: function(formData, jqForm, options) {
			
		}
	});
	
	/*$.ajax({
		type : "post",
		url : url,
		data : $(frm).serializeJSON(),
		datatype : "json",
		contentType: "application/json;charset=utf-8",
		enctype: "multipart/form-data",
		success : function(data) {
			if (data != null && data.message != null && data.message != undefined) {
				alert(data.message.trim());
			}
			
			if (callbackFunction != null && callbackFunction != undefined) {
				callbackFunction(data); //User Function Call
			}
		},
		error : function(xhr, status, err) {
			var responseText = xhr.responseText;

			if(xhr.status == 500 || xhr.status == 404) {
				responseText = responseText.replace('{', '').replace('}', '').replace(/[\"]/g,'');
				var alertDoc = new DOMParser().parseFromString(responseText, "text/html");
				alert(alertDoc.body.innerHTML);
			} else {
				responseText = responseText.replace('{', '').replace('}', '').replace(/[\"]/g,'');
				responseText = responseText.substring(responseText.indexOf(':') + 1).trim();

				if(responseText.indexOf("login.html") != -1){
					alert('로그인 세션이 종료되었습니다. 메인페이지로 이동합니다.');
					location.href = '/com/portal/index.do';
				}else{
					alert(responseText);
				}
			}
			if (errorCallbackFunction != null && errorCallbackFunction != undefined && errorCallbackFunction != false) {
				errorCallbackFunction(); // User Function Call
			}
		}
	});*/
}
