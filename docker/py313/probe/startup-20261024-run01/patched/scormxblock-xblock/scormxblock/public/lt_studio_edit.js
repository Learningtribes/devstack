/* Javascript for StudioEditableXBlockMixin. */
function StudioEditableXBlockMixin(runtime, element) {
    "use strict";
    function doNothing(attr) {
        return
    }
    var gettext = window.gettext || function (t) {return t};
    var LearningTribes = window.LearningTribes || {};
    if(!runtime.notify){
        runtime.notify = doNothing;
    }
    var fields = [];
    var tinyMceAvailable = (typeof $.fn.tinymce !== 'undefined'); // Studio includes a copy of tinyMCE and its jQuery plugin
    var datepickerAvailable = (typeof $.fn.datepicker !== 'undefined'); // Studio includes datepicker jQuery plugin

    $(element).find('.field-file-control').each(function () {
        var $field = $(this);
        var $wrapper = $field.closest('li');
        var $resetButton = $wrapper.find('button.setting-clear');
        var $preview = $wrapper.find('.setting-preview')
        var $info = $wrapper.find('.info')

        fields.push({
            name: $wrapper.data('field-name'),
            isSet: function () {
                return $wrapper.hasClass('is-set');
            },
            hasEditor: function () {
                return false;
            },
            val: function () {
                return $field.data('value')
            },
            file: function () {
                return $field.prop('files')[0]
            },
            files: function () {
                return Promise.all(
                    Array.from($wrapper[0].querySelectorAll('.option-input')).map(function ($option) {
                        return fetch($option.src)
                            .then(function (response) {return response.blob()})
                            .then(function (blob) {
                                var filename = $option.src.startsWith('blob') ? ($option.src.split('-').pop() + '.' + blob.type.split('/').pop()) : $option.src.split('@').pop()
                                return new File([blob], filename, {type: blob.type})
                            })
                    })
                )
            },
        });
        $field.bind("change", function () {
            // Field value has been modified:
            $wrapper.addClass('is-set');
            $resetButton.removeClass('inactive').addClass('active');
            var file = this.files && this.files[0]
            $info.text(file ? file.name : '');

            if (this.id == 'xb-field-edit-scorm_pkg' && file) {
                var fileSize = file.size;
                if (fileSize > 800 * 1024 * 1024) {
                    LearningTribes.Notification.Error({
                        title: gettext("Studio's having trouble saving your work"),
                        closeIcon: true,
                        message: gettext("Your file is too large.")
                    });
                }
            }

            if (this.accept && this.accept.startsWith('image/') && file) {
                var value = URL.createObjectURL(file)
                $field.data('value', value)
                renderFieldValuePreview(value)
            }
        });
        $resetButton.click(function () {
            $wrapper.removeClass('is-set');
            $resetButton.removeClass('active').addClass('inactive');
            $('#alert-field-file').addClass('hidden');
            $info.text('');
            $preview.find('.option').removeClass('active')
            setFieldValue($wrapper.attr('data-default'))
        });

        $field.parent().on('allowDrop', function (e) {e.preventDefault()})
        $field.parent().on('drag', function (e) {e.dataTransfer.setData("text", e.target.id)})
        $field.parent().on('drop', function (e) {
            e.preventDefault();
            $field.prop('files', e.originalEvent.dataTransfer.files).change();
            $info.text((e.originalEvent.dataTransfer.files[0] || {}).name || '');
        })

        $preview.find('.option').on('click', function () {
            $wrapper.addClass('is-set')
            $resetButton.addClass('active').removeClass('inactive')
            setFieldValue(this.alt)
        })

        function renderFieldValuePreview (imageUrl) {
            if (!imageUrl) return

            var $options = $preview.find('.option')
            var optionUrls = Array.from($options).map(function ($option) {return $option.alt})

            $options.each(function () {
                this.classList.remove('active')
            })

            if (optionUrls.includes(imageUrl)) {
                $options.each(function () {
                    if (this.alt == imageUrl) this.classList.add('active')
                })
            } else {
                var $option = $(
                    '<div class="option-wrapper">' +
                        '<img class="option option-input active" src="' + imageUrl + '" alt="' + imageUrl + '" />' +
                        '<i class="icon icon--active fa-solid fa-circle-check"></i>' +
                        '<i class="icon icon--inactive fa-solid fa-circle-minus"></i>' +
                    '</div>'
                ).appendTo($preview)
                $option.find('.option').on('click', function () {
                    $wrapper.addClass('is-set')
                    $resetButton.addClass('active').removeClass('inactive')
                    setFieldValue(this.alt)
                })
                $option.find('.icon--inactive').on('click', handleOptionInactivate)
            }
        }

        renderFieldValuePreview($field.data('value'))

        $preview.find('.icon--inactive').on('click', handleOptionInactivate)

        function handleOptionInactivate () {
            this.parentElement.remove()
        }

        function setFieldValue (value) {
            $field.val(undefined).change()
            $field.data('value', value)
            renderFieldValuePreview(value)
        }
    });

    $(element).find('#alert-field-close').bind('click', function () {
        $('#alert-field-file').addClass('hidden');
    })

    $(element).find('.field-data-control').each(function () {
        var $field = $(this);
        var $wrapper = $field.closest('li');
        var $resetButton = $wrapper.find('button.setting-clear');
        var type = $wrapper.data('cast');
        fields.push({
            name: $wrapper.data('field-name'),
            isSet: function () {
                return $wrapper.hasClass('is-set');
            },
            hasEditor: function () {
                return tinyMceAvailable && $field.tinymce();
            },
            val: function () {
                var val = $field.val();
                // Cast values to the appropriate type so that we send nice clean JSON over the wire:
                if (type == 'boolean')
                    return (val == 'true' || val == '1');
                if (type == "integer")
                    return parseInt(val, 10);
                if (type == "float")
                    return parseFloat(val);
                if (type == "generic" || type == "list" || type == "set") {
                    val = val.trim();
                    if (val === "")
                        val = null;
                    else
                        val = JSON.parse(val); // TODO: handle parse errors
                }
                return val;
            },
            removeEditor: function () {
                $field.tinymce().remove();
            }
        });
        var fieldChanged = function () {
            // Field value has been modified:
            $wrapper.addClass('is-set');
            $resetButton.removeClass('inactive').addClass('active');
        };
        $field.bind("change input paste", fieldChanged);
        $resetButton.click(function () {
            $field.val($wrapper.attr('data-default')); // Use attr instead of data to force treating the default value as a string
            $wrapper.removeClass('is-set');
            $resetButton.removeClass('active').addClass('inactive');
            $('#alert-field-file').addClass('hidden');
        });
        if (type == 'html' && tinyMceAvailable) {
            tinyMCE.baseURL = baseUrl + "/js/vendor/tinymce/js/tinymce";
            $field.tinymce({
                theme: 'modern',
                skin: 'studio-tmce4',
                height: '200px',
                formats: {code: {inline: 'code'}},
                codemirror: {path: "" + baseUrl + "/js/vendor"},
                convert_urls: false,
                plugins: "link codemirror",
                menubar: false,
                statusbar: false,
                toolbar_items_size: 'small',
                toolbar: "formatselect | styleselect | bold italic underline forecolor wrapAsCode | bullist numlist outdent indent blockquote | link unlink | code",
                resize: "both",
                setup: function (ed) {
                    ed.on('change', fieldChanged);
                }
            });
        }

        if (type == 'datepicker' && datepickerAvailable) {
            $field.datepicker('destroy');
            $field.datepicker({dateFormat: "m/d/yy"});
        }
    });

    $(element).find('.wrapper-list-settings .list-set').each(function () {
        var $optionList = $(this);
        var $checkboxes = $(this).find('input');
        var $wrapper = $optionList.closest('li');
        var $resetButton = $wrapper.find('button.setting-clear');

        fields.push({
            name: $wrapper.data('field-name'),
            isSet: function () {
                return $wrapper.hasClass('is-set');
            },
            hasEditor: function () {
                return false;
            },
            val: function () {
                var val = [];
                $checkboxes.each(function () {
                    if ($(this).is(':checked')) {
                        val.push(JSON.parse($(this).val()));
                    }
                });
                return val;
            }
        });
        var fieldChanged = function () {
            // Field value has been modified:
            $wrapper.addClass('is-set');
            $resetButton.removeClass('inactive').addClass('active');
        };
        $checkboxes.bind("change input", fieldChanged);

        $resetButton.click(function () {
            var defaults = JSON.parse($wrapper.attr('data-default'));
            $checkboxes.each(function () {
                var val = JSON.parse($(this).val());
                $(this).prop('checked', defaults.indexOf(val) > -1);
            });
            $wrapper.removeClass('is-set');
            $resetButton.removeClass('active').addClass('inactive');
            $('#alert-field-file').addClass('hidden');
        });
    });

    function ajaxFail(jqXHR) {
        var message = gettext("This may be happening because of an error with our server or your internet connection. Try refreshing the page or making sure you are online.");
        if (jqXHR.responseText) { // Is there a more specific error message we can show?
            try {
                message = JSON.parse(jqXHR.responseText).error;
                if (typeof message === "object" && message.messages) {
                    // e.g. {"error": {"messages": [{"text": "Unknown user 'bob'!", "type": "error"}, ...]}} etc.
                    message = $.map(message.messages, function (msg) {
                        return msg.text;
                    }).join(", ");
                }
            } catch (error) {
                message = jqXHR.responseText.substr(0, 300);
            }
        }
        runtime.notify('error', {title: gettext("Unable to update settings"), message: message});
    }

    var studio_submit = function (data) {
        var handlerUrl = runtime.handlerUrl(element, 'submit_studio_edits');
        $.ajax({
            type: "POST",
            url: handlerUrl,
            data: JSON.stringify(data),
            dataType: "json",
            global: false,  // Disable Studio's error handling that conflicts with studio's notify('save') and notify('cancel') :-/
            success: function (response) {
                runtime.notify('save', {state: 'end', element: element});
            }
        }).fail(ajaxFail);
    };


    var upload_files = function (form, success) {
        var handlerUrl = runtime.handlerUrl(element, 'studio_upload_files');
        $.ajax({
            type: "POST",
            url: handlerUrl,
            data: form,
            cache: false,
            contentType: false,
            processData: false,
            dataType: 'html',
        }).done(success).fail(ajaxFail);
    };

    $(window).on('dragover', function(e) {e.preventDefault();});
    $(window).on('drop', function(e) {e.preventDefault();});

    $('.save-button', element).bind('click', async function (e) {
        e.preventDefault();
        runtime.notify('save', {state: 'start', message: gettext("Saving")});

        var values = {};
        var notSet = []; // List of field names that should be set to default values
        var fileForm = new FormData()
        for (var i in fields) {
            var field = fields[i];
            var files = field.files && await field.files()

            if (files && files.length) {
                for (var j in files) {
                    fileForm.append(field.name + 's[]', files[j])
                }
                if (field.isSet()) {
                    fileForm.append(field.name, field.val())
                }
            } else if (field.file) {
                var file = field.file()
                if (file) {
                    fileForm.append(field.name, file)
                } else if (field.isSet()) {
                    values[field.name] = field.val()
                }
            } else {
                if (field.isSet()) {
                    values[field.name] = field.val()
                } else {
                    notSet.push(field.name)
                }
            }

            // Remove TinyMCE instances to make sure jQuery does not try to access stale instances
            // when loading editor for another block:
            if (field.hasEditor()) {
                field.removeEditor();
            }
        }

        if (Array.from(fileForm.entries()).length > 0) {
            upload_files(fileForm, function () {
                studio_submit({values, defaults: notSet})
            })
        } else {
            studio_submit({values, defaults: notSet})
        }
    });

    var $element = $(element);
    $element.find('.cancel-button').bind('click', function (e) {
        // Remove TinyMCE instances to make sure jQuery does not try to access stale instances
        // when loading editor for another block:
        for (var i in fields) {
            var field = fields[i];
            if (field.hasEditor()) {
                field.removeEditor();
            }
        }
        e.preventDefault();
        runtime.notify('cancel', {});
    });

    if (LearningTribes && LearningTribes.QuestionMark) {
        var $wrappers = $('.wrapper-comp-settings .question-mark-wrapper')
        $wrappers.each(function(i, wrapper){
            new LearningTribes.QuestionMark(wrapper)
        })
    }

    function renderSwithcher(wrapper) {
        var $select = $(wrapper).prev();
        new LearningTribes.Switcher(wrapper, $select.find('option:selected').val() === '1' ? 'true' : 'false',
            function (checked) {
                var checkedStr = checked ? '1' : '0';
                $select.find('option').removeAttr('selected')
                $select.find('option[value='+checkedStr+']').attr('selected', 'selected')
                $select.closest('.comp-setting-entry').attr('data-value', checked ? 'true' : 'false')
            }
        )
        var $li = $select.closest('.field')
        $li.addClass('is-set')
    }
    if (LearningTribes && LearningTribes.Switcher) {
        var $wrappers = $('.wrapper-comp-settings').find('.switcher-wrapper');
        $wrappers.each(function(i, wrapper){
            renderSwithcher(wrapper)
        })
    }
}
