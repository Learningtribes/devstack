 function ExternalContentXBlock(runtime, element) {
    $(function ($) {
        /* Here's where you'd do things on page load. */
    });

    if ($('.externalityxblock_block').length > 0) {
        // In LMS page, we mark as completed for this user.
        window.onload = function () {
            setTimeout(function () {
                var data = {
                    'completion': 1.0,
                };
                var handlerUrl = runtime.handlerUrl(element, 'publish_completion');

                $.post(handlerUrl, JSON.stringify(data)).complete(function () {
                });
            }, 1000);

        };
    }

    function updateResList(activeTab) {
        var $resources = $(".supported-resources li.resource-item");
        var activeStatus = activeTab;

        $resources.each(function () {
            if (activeStatus == 'all-tags' || $(this).data('status').split(',').includes(activeStatus) ) {
                $(this).show();
            } else {
                $(this).hide();
            }
        })

    }

    $('.supported-tags-nav > li', element).bind('click', function() {
        $(this).find('.btn-link').addClass('active-section');
        $(this).siblings().find('.btn-link').removeClass('active-section');
        updateResList($(this).attr('id'));

    });

}
