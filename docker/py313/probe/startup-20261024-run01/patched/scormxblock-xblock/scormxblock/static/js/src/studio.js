(function () {
  var requestIdleCallback = window.requestIdleCallback || window.requestAnimationFrame;

  requestIdleCallback(function () {
    waitUntilDOM('.xblock-author_view.xblock-initialized', function () {
      scrollToBottomWhenToggleNewTab();

      // only first time is javascript excuted along with author_view.html, so we need to listen to click event
      document.querySelectorAll('.studio-xblock-preview-scormxblock .header-actions .edit-button').forEach(function ($button) {
        $button.addEventListener('click', function () {scrollToBottomWhenToggleNewTab();});
      });
    });
  });

  function scrollToBottomWhenToggleNewTab () {
    requestIdleCallback(function () {
      waitUntilDOM('.xblock-studio_view-scormxblock.xblock-initialized', function () {
        var $newTabSwitcher = document.querySelector('#xb-field-edit-open_new_tab + span.switcher-wrapper > div');

        if ($newTabSwitcher) $newTabSwitcher.addEventListener('click', function () {scrollToBottom('#settings-tab > div.list-input.settings-list')});
      });
    });

    function scrollToBottom (selector) {
      var $container = document.querySelector(selector);
      if ($container && $container.children.length) {
        var $lastChild = $container.children[$container.children.length - 1];
        requestAnimationFrame(function () {
          if ($lastChild.scrollIntoViewIfNeeded) $lastChild.scrollIntoViewIfNeeded(false);
          else $lastChild.scrollIntoView({behavior: 'smooth', block: 'nearest', inline: 'start'});
        });
      }
    }
  }

  function waitUntilDOM (selector, cb) {
    requestAnimationFrame(function () {
      console.count('wait for', selector);
      if (document.querySelector(selector)) requestAnimationFrame(cb);
      else requestAnimationFrame(function () {waitUntilDOM(selector, cb)});
    })
  }
})();
