/* Javascript for LbmDoneXBlock. */
function updateCheck(element) {
    if ($('#lbmdonexblock-checkbox', element).prop("checked")) {
        $('.lbmdonexblock_block', element).addClass("done");
        $('.fa-check-square-o', element).removeClass("invisible").addClass("visible");
        $('.fa-square-o', element).removeClass("visible").addClass("invisible");
    } else {
        $('.lbmdonexblock_block', element).removeClass("done");
        $('.fa-square-o', element).removeClass("invisible").addClass("visible");
        $('.fa-check-square-o', element).removeClass("visible").addClass("invisible");
    }
}

function LbmDoneXBlock(runtime, element, data) {
    $('#lbmdonexblock-checkbox', element).prop("checked", data.done);
    updateCheck(element);
    var handlerUrl = runtime.handlerUrl(element, 'toggle_button');

    $(function ($) {
        var lbmRed = $('#course-menu').find('> ol > li .active').css('border-bottom-color');
        if (lbmRed !== undefined) {
            $('.lbmdonexblock_block').css('background-color', lbmRed);
        }

        var checkbox = $('#lbmdonexblock-checkbox', element);
        var pending = false;
        $('.lbmdonexblock_block', element).click(function(event) {
            // A label click also activates its checkbox. Handle it only once.
            event.preventDefault();
            if (pending) {
                return;
            }
            pending = true;
            var current_done = checkbox.prop("checked");
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify({}),
                success: function(return_data) {
                    checkbox.prop("checked", return_data.done);
                    updateCheck(element);
                },
                error: function() {
                    checkbox.prop("checked", current_done);
                    updateCheck(element);
                },
                complete: function() {
                    pending = false;
                }
            });
        });

    });
}
