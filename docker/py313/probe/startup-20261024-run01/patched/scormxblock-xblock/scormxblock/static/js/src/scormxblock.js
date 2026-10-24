    function ScormXBlock(runtime, element, settings) {
        "use strict";

        const commitUrl = runtime.handlerUrl(element, 'scorm_commit');
        const ios_commitUrl = runtime.handlerUrl(element, 'scorm_ios_commit');
        const enforce_commitUrl = runtime.handlerUrl(element, 'scorm_enforce_commit');
        const getValueUrl = runtime.handlerUrl(element, 'scorm_get_value');
        const syncScoreUrl = runtime.handlerUrl(element, 'sync_score_value')
        const syncRuntimeInfoUrl = runtime.handlerUrl(element, 'sync_runtime_info')
        const package_version = settings['scorm_pkg_version_value'];
        const package_date = settings['scorm_pkg_modified_value'];
        const ratio_value = settings['ratio_value'];
        let usageId = (element.dataset && element.dataset.usageId) || 
                      $(element).data('usage-id') || 
                      $(element).attr('data-usage-id') || 
                      $(element).closest('.xblock').data('usage-id') ||
                      $(element).closest('.xblock').attr('data-usage-id');
        let pendingValues = null;
        let scormRuntimeInfo;
        var timerId;

        function deepCopy(obj) {
            return JSON.parse(JSON.stringify(obj));
        }

        function isInLMS(xblockElement) {
            return $(xblockElement).closest('.xblock').hasClass('xblock-student_view');
        }

        let container = isInLMS(element) ? '.xblock-student_view' : '.xblock-author_view';
        let iframe = $(container + '[data-usage-id="'+usageId+'"] #scorm-object-frame');
        let iframe_container = $(container + '[data-usage-id="'+usageId+'"] .scorm_object_container');

        function quitFullscreen() {
            iframe_container.removeClass('fullscreen_scormxblock_view');
/*
            function updateQueryParam(url, key, value) {
                var separator = url.indexOf('?') !== -1 ? '&' : '?';
                var re = new RegExp('([?&])' + key + '=[^&]*');
                if (re.test(url)) {
                    return url.replace(re, '$1' + key + '=' + encodeURIComponent(value));
                } else {
                    return url + separator + key + '=' + encodeURIComponent(value);
                }
            }
            // For some SCORM pkgs, they show "Ending Text" after learner clicks on "Exit Button".
            // So we refresh the iframe.src to reload the content before the learner clicks the "Launch Button" again.
            let newURL = updateQueryParam(iframe[0].src, 'lt_refresh_time', new Date().getTime());
            iframe[0].src = newURL;
            iframe.attr('data-src', newURL);
*/
        }

        function scormInit() {
            var ratios = {
                '4:3': 0.75,
                '16:9': 0.5625,
                '1:1': 1,
            }
            var resetIframeSize = function () {
              iframe.height(iframe.width() * ratios[ratio_value]);
            }
            if (iframe.length){
              $(window).resize(function () {
                resetIframeSize();
              })
              iframe.on('load', resetIframeSize)
            }

            $('.exit-fullscreen-button').click(quitFullscreen)

            let launch_button_selector = container + '[data-usage-id="'+usageId+'"] .launch-button';

            $(launch_button_selector).click(function() {
                if (!iframe_container.hasClass('fullscreen_scormxblock_view')) {
                    iframe_container.addClass('fullscreen_scormxblock_view');
                }
            })

            // Get runtime score value due to unexpected terminal action
            timerId = setInterval(Enforce_Commit, 2000);
            setTimeout(function(){ syncScoreValue()},2000);
            setTimeout(function(){ syncScoreValue()},5000);
            setTimeout(function(){ syncScoreValue()},10000);

        }

        function syncScormRuntimeInfo () {
            if (scormRuntimeInfo) {
                scormRuntimeInfo = Object.assign(scormRuntimeInfo, pendingValues || {})
                return
            }

            fetch(syncRuntimeInfoUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': GetCookie('csrftoken'),
                },
                body: JSON.stringify(getPackageData())
            }).then(resp => resp.json().then(resp => {
                if (resp.error) {
                    LearningTribes.Notification.Error({
                        title: window.gettext("We're having trouble saving your work"),
                        message: window.gettext(resp.error),
                    });
                } else {
                    scormRuntimeInfo = resp.value
                }
            }))
        }

        function getValueInRuntimeInfo (name) {
            if (!scormRuntimeInfo) return
            return scormRuntimeInfo[name]
        }

        function Initialize(value) {
            return pingServer() ? "true": "false";
        }

        function Terminate(value) {
            Commit(value);
            clearInterval(timerId);
            return 'true';
        }

        function GetValue(name) {
            const value = getValueInRuntimeInfo(name)
            if (value !== undefined) return value

            const data = getPackageData();
            data['name'] = name;

            const resp = $.ajax({
                type: "POST",
                url: getValueUrl,
                data: JSON.stringify(data),
                async: false
            });
            const content = JSON.parse(resp.responseText);
            if(content.error) {
                LearningTribes.Notification.Error({
                    title: window.gettext("We're having trouble saving your work"),
                    message: window.gettext(content.error),
                });
            }
            return content.value;
        }

        function SetValue(name, value) {
            pendingValues[name] = value;
            return 'true';
        }

        function CheckChrome() {
            var isChromium = window.chrome;
            var winNav = window.navigator;
            var vendorName = winNav.vendor;
            var isOpera = typeof window.opr !== "undefined";
            var isIEedge = winNav.userAgent.indexOf("Edge") > -1;
            var isIOSChrome = winNav.userAgent.match("CriOS");
            var chrome_commit = false

            if (isIOSChrome) {
                chrome_commit = true
            } else if(
              isChromium !== null &&
              typeof isChromium !== "undefined" &&
              vendorName === "Google Inc." &&
              isOpera === false &&
              isIEedge === false
            ) {
                chrome_commit = true
            }

            return chrome_commit;
        }

        function CheckSafari() {
            var isSafari = false;
            var winNav = window.navigator;
            if (winNav.userAgent.indexOf('Safari') != -1 && winNav.userAgent.indexOf('Chrome') == -1) {
                isSafari = true
            }

            return isSafari;
        }

        function CheckSafariMobile() {
            var isSafariMobile = false;
            var winNav = window.navigator;
            if (winNav.userAgent.indexOf('Safari') != -1 && winNav.userAgent.indexOf('Chrome') == -1 && winNav.userAgent.indexOf('Mobile') != -1) {
                isSafariMobile = true
            }

            return isSafariMobile;
        }

        function GetCookie(name) {
          if (!document.cookie) {
            return null;
          }

          const xsrfCookies = document.cookie.split(';')
            .map(function(c) {
                return c.trim();
            }).filter(function(c) {
                return c.startsWith(name + '=');
            });
          if (xsrfCookies.length === 0) {
            return null;
          }
          return decodeURIComponent(xsrfCookies[0].split('=')[1]);
        }


        window.onpagehide = function () {
            if (CheckSafariMobile()) {
                Extra_Commit();
            }
        };

        document.onvisibilitychange = function () {
            if (CheckSafariMobile() && (document.visibilityState === 'hidden')) {
                Extra_Commit();
            }
        };

        window.onbeforeunload = function () {
            Extra_Commit();
        };

        function Extra_Commit() {
            performCommit(commitUrl);

            return 'true';
        }

        function Enforce_Commit() {
            if (('cmi.score.raw' in pendingValues && 'cmi.score.max' in pendingValues && 'cmi.score.min' in pendingValues) || ('cmi.core.score.raw' in pendingValues && 'cmi.core.score.max' in pendingValues && 'cmi.core.score.min' in pendingValues) || ('cmi.core.lesson_status' in pendingValues)  || ('cmi.success_status' in pendingValues) || ('cmi.score.scaled' in pendingValues)) {
                performCommit(enforce_commitUrl);
            }
            return 'true';
        }

        function performCommit(url) {
            let commit_success = false;
            // Clone a pendingValues for commit
            const clonedPendingValues = deepCopy(pendingValues);
            // Reset the pendingValues, so other commit function will not make duplicated commit.
            pendingValues = getPackageData();

            $.ajax({
                type: "POST",
                url: url,
                data: JSON.stringify(clonedPendingValues),
                contentType: 'application/json;charset=UTF-8',
                headers: {
                    'X-CSRFToken': GetCookie('csrftoken')
                },
                async: false, // Synchronous request for SCORM compatibility
                success: function(content) {
                    if(content.error) {
                        LearningTribes.Notification.Error({
                            title: window.gettext("We're having trouble saving your work"),
                            message: window.gettext(content.error),
                        });
                    } else {
                        commit_success = true;
                    }

                    if (typeof content['scorm_score_value'] !== "undefined") {
                        $(".lesson_score", element).html(content['scorm_score_value']);
                    }
                    $(".success_status", element).html(content['scorm_status_value']);
                },
                error: function(xhr, status, error) {
                    if (xhr.status === 403) {   // Maybe it's a CSRF token error
                        LearningTribes.Notification.Error({
                            title: window.gettext("We're having trouble saving your work"),
                            message: window.gettext("An error has occurred. Please try reloading the page."),
                        });
                    } else if (!navigator.onLine && status === 'error') {
                        LearningTribes.Notification.Error({
                            title: window.gettext("We're having trouble saving your work"),
                            message: window.gettext("Please check your network connection."),
                        });
                    }
                },
                complete: function() {
                    if (commit_success === false) { // recover cloned values if get commit failure
                        pendingValues = Object.assign({}, clonedPendingValues, pendingValues || {});
                    }
                }
            });
        }

        function Commit(value) {
            performCommit(commitUrl);

            return 'true';
        }

        function initPendingValues(){
            syncScormRuntimeInfo();
            pendingValues = getPackageData();
        }


        function GetLastError() {
            // console.log(version + ' GetLastError');
            return 0;
        }

        function GetErrorString(errCode) {
            // console.log(version + ' GetErrorString: ' + errCode);
            return '';
        }

        function GetDiagnostic(errCode) {
            // console.log(version + ' GetDiagnostic: ' + errCode);
            return 'true';
        }


        function SCORM_12_API() {
            this.LMSInitialize = Initialize;
            this.LMSFinish = Terminate;
            this.LMSGetValue = GetValue;
            this.LMSSetValue = SetValue;
            this.LMSCommit = Commit;
            this.LMSGetLastError = GetLastError;
            this.LMSGetErrorString = GetErrorString;
            this.LMSGetDiagnostic = GetDiagnostic;
        }

        function SCORM_2004_API() {
            this.Initialize = Initialize;
            this.Terminate = Terminate;
            this.GetValue = GetValue;
            this.SetValue = SetValue;
            this.Commit = Commit;
            this.GetLastError = GetLastError;
            this.GetErrorString = GetErrorString;
            this.GetDiagnostic = GetDiagnostic;
        }

        function getPackageData() {
            return {
                'package_date': package_date,
                'package_version': package_version
            }
        }

        function pingServer() {
            const resp = $.ajax({
                type: "GET",
                url: runtime.handlerUrl(element, 'ping'),
                async: false
            });
            return resp.status === 200;

        }

        function syncScoreValue() {
            $.ajax({
                type: "GET",
                url: syncScoreUrl,
                async: true,
                success: function(response) {
                    $(".lesson_score", element).html(response['scorm_score_value']);
                }
            });
        }

        $(function ($) {
            scormInit();
            initPendingValues();
            window.API = new SCORM_12_API();
            window.API_1484_11 = new SCORM_2004_API();

            document.addEventListener('keyup', function(e) {
                if (e.keyCode === 27 || e.key === 'Escape') {
                    console.log('ESC pressed!');
                    quitFullscreen();
                }
            });

            if (!window.loadingScormModuleMap) {
                window.loadingScormModuleMap = {}
            }
            if (!window.loadedScormModules) {
                window.loadedScormModules = [];
            }
            Array.from(document.querySelectorAll('.xblock-student_view-scormxblock')).filter(function(xblock) {
                return xblock.querySelector('.scorm_object')
            }).forEach(function(xblock, i) {
                var xblockUsageId = (xblock.dataset && xblock.dataset.usageId) || 
                                   $(xblock).data('usage-id') || 
                                   $(xblock).attr('data-usage-id');
                if (!usageId || xblockUsageId !== usageId) return
                if (window.loadingScormModuleMap[usageId] !== undefined) return

                var tomb = setInterval(() => {
                    if (window.loadedScormModules.length === i) loadScormIFrame();
                }, i * 2000 + 1000);

                function loadScormIFrame() {
                    if (window.loadingScormModuleMap[usageId] !== undefined) return
                    window.loadingScormModuleMap[usageId] = tomb

                    window.API = new SCORM_12_API();
                    window.API_1484_11 = new SCORM_2004_API();
                    var $iFrame = xblock.querySelector('.scorm_object');
                    $iFrame.src = $iFrame.dataset.src;
                    $iFrame.onload = function() {
                        window.loadedScormModules.push(usageId)
                        clearInterval(window.loadingScormModuleMap[usageId])

                        // A SCORM pkg can have more than 1 <iframe>, we just setup event listener for the first one:
                        const keyEventTargetFrame = $iFrame.contentWindow.document.querySelector('iframe') || $iFrame;
                        keyEventTargetFrame.contentWindow.document.addEventListener('keyup', e => {
                            if (e.keyCode === 27 || e.key === 'Escape') {
                                quitFullscreen();       // Quite full screen mode
                            }
                        })
                    }
                }
            })

        });
    }
