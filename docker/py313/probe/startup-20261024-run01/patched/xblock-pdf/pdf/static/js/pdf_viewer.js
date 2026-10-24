/* Javascript for pdfXBlock. */
function pdfXBlockInitView(runtime, element, json) {
    /* Weird behaviour :
     * In the LMS, element is the DOM container.
     * In the CMS, element is the jQuery object associated*
     * So here I make sure element is the jQuery object */
    if (element.innerHTML) {
        element = $(element);
    }

    const $element = element[0]
    $element.querySelectorAll(".pdf-h5-container[data='']").forEach($c => {
        $c.setAttribute('data', `/xblock/resources/pdf/public/web/viewer.html?file=${($c.dataset.src && $c.dataset.src[0] === '/') ? $c.dataset.src : json.url}`)
    })
    $element.querySelectorAll(".pdf-embed-container[data='']").forEach($c => {
        $c.setAttribute('data', `${$c.dataset.src}#view=FitH&toolbar=${json.allow_download ? 1 : 0}`)
    })

    $(function () {
        element.find('.pdf-download-button').on('click', function () {
            var handlerUrl = runtime.handlerUrl(element, 'on_download');
            $.post(handlerUrl, '{}');
        });
    });
}

window.pdfXBlockInitView = pdfXBlockInitView;
