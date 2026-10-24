/* Javascript for pdfXBlock. */
function pdfXBlockInitEdit(runtime, element) {
    $(element).find('.action-cancel').bind('click', function () {
        runtime.notify('cancel', {});
        $('.pdf_placeholder').hide();
    });

    $(element).find('.action-save').bind('click', function () {
        var data = {
            'display_name': $('#pdf_edit_display_name').val(),
            url: $('#pdf_edit_url').val().trim(),
            'allow_download': $('#pdf_edit_allow_download').val(),
            'source_text': $('#pdf_edit_source_text').val(),
            'source_url': $('#pdf_edit_source_url').val()
        };

        if (data.url && data.url[0] !== '/' && data.url[0] !== 'h') {
            data.url = window.location.href.split(':')[0] + '://' + data.url;
            // data.url = '/' + data.url.split('/')[1]
        }

        runtime.notify('save', { state: 'start' });

        var handlerUrl = runtime.handlerUrl(element, 'save_pdf');
        $.post(handlerUrl, JSON.stringify(data)).done(function (response) {
            if (response.result === 'success') {
                runtime.notify('save', { state: 'end' });
            }
            else {
                runtime.notify('error', { msg: response.message });
            }
        });

        $('.pdf_placeholder').hide();
    });


    $(element).find("#browse-button").bind('click', function (){
        $('#file-input').click();
    });

    var fileInput = $('#file-input')[0];
    fileInput.onchange = function () {
        var file = fileInput.files[0];
        var formData = new FormData();
        formData.append('file', file);
        var request = new XMLHttpRequest();
        var course_key = element[0].dataset['usageId'].split('+', 3).join('+').replace('block', 'course');
        var upload_url = '/assets/' + course_key + '/';
        var csrftoken = $.cookie('csrftoken');
        var alertField = $('.alert-field');
        request.open("POST", upload_url);
        request.setRequestHeader("X-CSRFToken", csrftoken);
        request.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        request.setRequestHeader('Accept', 'application/json');
        alertField.removeClass('hidden');
        alertField.addClass('alert-info');
        alertField.removeClass('alert-success');
        alertField.removeClass('alert-error');
        $('#alert-info-text').removeClass('hidden');
        $('#alert-success-text').addClass('hidden');
        $('#alert-error-text').addClass('hidden');
        request.onerror = function () {
           alertField.removeClass('alert-info');
           alertField.removeClass('alert-success');
           alertField.addClass('alert-error');
           $('#alert-info-text').addClass('hidden');
           $('#alert-success-text').addClass('hidden');
           $('#alert-error-text').removeClass('hidden');
        };
        request.onload = function () {
            var response = JSON.parse(request.responseText);
            if (request.status === 200) {
                $('#pdf_edit_url').val(response.asset.external_url);
               alertField.removeClass('alert-info');
               alertField.addClass('alert-success');
               alertField.removeClass('alert-error');
               $('#alert-info-text').addClass('hidden');
               $('#alert-success-text').removeClass('hidden');
               $('#alert-error-text').addClass('hidden');
            } else {
               alertField.removeClass('alert-info');
               alertField.removeClass('alert-success');
               alertField.addClass('alert-error');
               $('#alert-info-text').addClass('hidden');
               $('#alert-success-text').addClass('hidden');
               $('#alert-error-text').removeClass('hidden');
            }
        };
        request.send(formData);
    };

    var dropZone = $('.drop-zone')[0];
    $('.pdf_placeholder').show();

    dropZone.ondragenter = function() {
      dropZone.style.background = "rgba(0, 240, 240, 0.2)";
    };
    dropZone.ondragover = function() {
      dropZone.style.background = "rgba(0, 240, 240, 0.2)";
      return false;
    };
    dropZone.ondragleave = function() {
      dropZone.style.background = "white";
    };
    dropZone.ondrop = function(ev) {
      var oFile = ev.dataTransfer.files[0];
      var request = new XMLHttpRequest();
      var reader = new FileReader();
      var course_key = element[0].dataset['usageId'].split('+', 3).join('+').replace('block', 'course');
      var upload_url = '/assets/' + course_key + '/';
      var csrftoken = $.cookie('csrftoken');
      var alertField = $('.alert-field');
      reader.readAsDataURL(oFile, 'base64');
      var formData = new FormData();
      formData.append("file", oFile);
      reader.onload = function(e) {
        request.open("POST", upload_url);
        request.setRequestHeader("X-CSRFToken", csrftoken);
        request.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        request.setRequestHeader('Accept', 'application/json');
        alertField.removeClass('hidden');
       alertField.addClass('alert-info');
       alertField.removeClass('alert-success');
       alertField.removeClass('alert-error');
       $('#alert-info-text').removeClass('hidden');
       $('#alert-success-text').addClass('hidden');
       $('#alert-error-text').addClass('hidden');
        request.onerror = function () {
           alertField.removeClass('alert-info');
           alertField.removeClass('alert-success');
           alertField.addClass('alert-error');
           $('#alert-info-text').addClass('hidden');
           $('#alert-success-text').addClass('hidden');
           $('#alert-error-text').removeClass('hidden');
        };
        request.onload = function () {
            var response = JSON.parse(request.responseText);
            if (request.status === 200) {
                $('#pdf_edit_url').val(response.asset.external_url);
               alertField.removeClass('alert-info');
               alertField.addClass('alert-success');
               alertField.removeClass('alert-error');
               $('#alert-info-text').addClass('hidden');
               $('#alert-success-text').removeClass('hidden');
               $('#alert-error-text').addClass('hidden');
            } else {
               alertField.removeClass('alert-info');
               alertField.removeClass('alert-success');
               alertField.addClass('alert-error');
               $('#alert-info-text').addClass('hidden');
               $('#alert-success-text').addClass('hidden');
               $('#alert-error-text').removeClass('hidden');
            }
        };
        request.send(formData);
      };
      dropZone.style.background = "white";
      return false;
    };

    $('#alert-field-close')[0].onclick = function () {
        $('.alert-field').addClass('hidden');
    }

    if (LearningTribes && LearningTribes.QuestionMark) {
        $wrappers = $('.wrapper-comp-settings .question-mark-wrapper')
        $wrappers.each(function(i, wrapper){
            new LearningTribes.QuestionMark(wrapper)
        })
    }

    if (LearningTribes && LearningTribes.Switcher) {
        var switcher = $('.wrapper-comp-settings').find('.switcher-wrapper')[0];
        var $select = $('#pdf_edit_allow_download')
        new LearningTribes.Switcher(switcher, $select.find('option[selected]')[0].value.toLowerCase(),
            function(checked){
            var checkedStr = checked.toString();
            checkedStr = checkedStr[0].toUpperCase() + checkedStr.slice(1);
            $('#pdf_edit_allow_download').find('option[value='+checkedStr+']')
                .removeAttr('selected')
                .attr('selected', true)
            }
        )
    }

}
