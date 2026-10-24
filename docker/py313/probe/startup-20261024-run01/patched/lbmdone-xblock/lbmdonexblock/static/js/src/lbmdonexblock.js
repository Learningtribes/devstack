/* Javascript for LbmDoneXBlock. */
function updateCheck(element, data) {
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
    updateCheck(element, data);
    var handlerUrl = runtime.handlerUrl(element, 'toggle_button');

    $(function ($) {
        var lbmRed = $('#course-menu').find('> ol > li .active').css('border-bottom-color');
        if (lbmRed !== undefined) {
            $('.lbmdonexblock_block').css('background-color', lbmRed);
        }

        $('.lbmdonexblock_block', element).click(function() {
            var current_done = data.done;
            var to_done = !data.done;
            if (current_done != to_done) {
                $('#lbmdonexblock-checkbox', element).prop("checked", to_done.done);
            }
            updateCheck();
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify({}),
                success: function(return_data) {
                    $('#lbmdonexblock-checkbox', element).prop("checked", return_data.done);
                    updateCheck();
                },
                error: function() {
                    $('#lbmdonexblock-checkbox', element).prop("checked", current_done.done);
                    updateCheck();
                },
            });
        });

    });
}
