/* Javascript for ILTXBlock. */
function detectIE() {
    const ua = window.navigator.userAgent;

    const msie = ua.indexOf('MSIE ');
    if (msie > 0) {
        // IE 10 or older => return version number
        return parseInt(ua.substring(msie + 5, ua.indexOf('.', msie)), 10);
    }

    const trident = ua.indexOf('Trident/');
    if (trident > 0) {
        // IE 11 => return version number
        const rv = ua.indexOf('rv:');
        return parseInt(ua.substring(rv + 3, ua.indexOf('.', rv)), 10);
    }

    const edge = ua.indexOf('Edge/');
    if (edge > 0) {
        // Edge (IE 12+) => return version number
        return parseInt(ua.substring(edge + 5, ua.indexOf('.', edge)), 10);
    }

    // other browser
    return false;
}

function jsonToStr(jObj) {
    let resultStr = "";
    if (typeof(jObj) == 'string') {
        return jObj
    }
    else {
        for (var key in jObj) {
            if (jObj.hasOwnProperty(key)) {
                resultStr += (key + ": " + jObj[key] + '<br>');
            }
        }
    }
    return resultStr
}

String.prototype.endsWith = function (suffix) {
    return this.indexOf(suffix, this.length - suffix.length) !== -1;
};

Date.prototype.addHours = function (h) {
    this.setTime(this.getTime() + (h * 60 * 60 * 1000));
    return this;
};

Date.prototype.today = function () {
    return this.getFullYear() + '-' + (((this.getMonth() + 1) < 10) ? "0" : "") + (this.getMonth() + 1) + "-" + ((this.getDate() < 10) ? "0" : "") + this.getDate();
};

Date.prototype.timeNow = function () {
    return ((this.getHours() < 10) ? "0" : "") + this.getHours() + ":" + ((this.getMinutes() < 10) ? "0" : "") + this.getMinutes();
};

function ILTXBlock(runtime, element, init_args) {
    const handlerUrl = runtime.handlerUrl(element, 'student_handler');
    const addSessionUrl = runtime.handlerUrl(element, 'add_session');
    const delSessionUrl = runtime.handlerUrl(element, 'del_session');
    const enrollmentUrl = runtime.handlerUrl(element, 'toggle_enrollment');
    const enrolledUsersUrl = runtime.handlerUrl(element, 'get_enrolled_users');
    const gradeUrl = runtime.handlerUrl(element, 'grade_users');
    const batchEnrollUrl = runtime.handlerUrl(element, 'batch_enroll');
    const batchUnenrollUrl = runtime.handlerUrl(element, 'batch_unenroll');
    const accommodationUrl = runtime.handlerUrl(element, 'accommodation_validate');
    const updateAckUrl = runtime.handlerUrl(element, 'update_ack_attendance');
    const updateAcceptedRequestUrl = runtime.handlerUrl(element, 'batch_update_accepted_requests');
    const switchSessionUrl = runtime.handlerUrl(element, 'batch_switch_session');
    const acceptRequestUrl = runtime.handlerUrl(element, 'batch_accept_requests');

    function switchManagement(m_id) {
        var ls = ['1', '2', '3', '4'];
        for(var i in ls){
            var manage_id = "#ilt-management-" + ls[i];
            if(ls[i] == m_id){
                $(manage_id).css("display", "block");
            }
            else {
                $(manage_id).css("display", "none");
            }
        }
    }

    $(document).on("mouseenter", ".ilt-management-tabs > li", function () {
        var $container = $(this),
            $anchor = $container.find('a'),
            $neighbour = $container.siblings().find('a'),
            $staff_actions = $(".ilt-staff-actions"),
            min_height = parseInt($staff_actions.css('min-height').replace('px', ''));
        $anchor.addClass('ilt-hover');
        $neighbour.removeClass('ilt-hover');
        switchManagement($container.data('id'));
        var height = parseInt($staff_actions.css('height').replace('px', ''));
        if (height > min_height) {
            $staff_actions.css('min-height', height);
        }
    });

    Vue.http.interceptors.push(function (request, next) {
        if (request.method === 'POST') {
            request.headers.set('X-CSRFToken', $.cookie('csrftoken'));
        }
        next();
    });

    Vue.component('timepicker', {
        template: '<input v-bind:value="value">',
        props: ['value'],
        mounted: function () {
            const self = this;
            $(self.$el).timepicker({
                'timeFormat': 'H:i',
                'step': 15
            });
            $(this.$el).on('change', function (e) {
                self.$emit("input", e.target.value);
            });
        }
    });

    function errorGetILT(error) {
        ILTView.saveMsg = "failed";
    }

    function successGetILT(resp, updateMsg) {
        resp.json().then(function (data) {
            ILTView.domain = data.domain;
            ILTView.title = data.title;
            ILTView.course_name = data.course_name;
            ILTView.description = data.description;
            ILTView.weight = data.weight;
            ILTView.sessions = data.sessions;
            ILTView.enrollment = data.enrollment;
            ILTView.isStaff = data.is_staff;
            ILTView.isAdmin = data.is_admin;
            ILTView.timezones = data.timezones;
            ILTView.dropdown_list = data.dropdown_list;
            ILTView.date_format = data.date_format;
            ILTView.optional_fields = data.ilt_optional_fields;
            ILTView.accommodation_enabled = data.accommodation;
            ILTView.accommodation_list = data.accommodation_list;
            ILTView.all_list = data.all_list;
            ILTView.checkbox_select_all_requests = false;
            ILTView.show_unenroll_button = data.show_unenroll_button;
            ILTView.course_id = data.course_id;
            ILTView.usage_id = data.usage_id;
            ILTView.bypass_validation_flag = data.bypass_validation_flag;
            ILTView.show_ilt_invitation = data.show_ilt_invitation;
            updateMsg && (ILTView.saveMsg = "succeed");

            if (data.deadline != null) {
                ILTView.deadline = data.deadline;
            }

            for (let i in ILTView.dropdown_list) {
                if (!ILTView.dropdown_list[i][1].includes("expire-for-student")) {
                    ILTView.hide_list_to_student = false;
                    ILTView.hide_list_to_accommodation_admin = false;
                    break
                }
                ILTView.hide_list_to_student = true;
                ILTView.hide_list_to_accommodation_admin = true;
            }

            for (let i in ILTView.dropdown_list) {
                if (!ILTView.dropdown_list[i][1].includes("expire-for-admin")) {
                    ILTView.hide_list_to_admin = false;
                    break
                }
                ILTView.hide_list_to_admin = true
            }

            var current_lang = $('html')[0].lang,
                datepicker_format = 'yy-mm-dd';
            if (current_lang == 'fr' || current_lang == 'ro') {
                datepicker_format = 'dd-mm-yy';
                ILTView.date_convert_format = 'DD-MM-YYYY'
            }

            ILTView.editSessions = data.sessions.map(function (item) {
                var nitem = item.slice();
                var start_at = nitem[1]['start_at'].split("T");
                var end_at = nitem[1]['end_at'].split("T");
                nitem[1]['start_at_date'] = moment(start_at[0]).format(ILTView.date_convert_format);
                nitem[1]['start_at_time'] = start_at[1];
                nitem[1]['end_at_date'] = moment(end_at[0]).format(ILTView.date_convert_format);
                nitem[1]['end_at_time'] = end_at[1];
                return nitem
            });
            if (ILTView.editSessions.length == 0) {
                ILTView.addSession()
            }
            if (data.enrollment) {
                for (var i = 0; i < ILTView.sessions.length; i++) {
                    if (ILTView.sessions[i][0] === data.enrollment[0]) {
                        ILTView.selectedSession = i;
                        break;
                    }
                }
            } else {
                ILTView.selectedSession = null;
            }

            Vue.component('datepicker', {
                template: '<input v-bind:value="value">',
                props: ['value'],
                mounted: function () {
                    const self = this;
                    $(self.$el).datepicker({
                        dateFormat: datepicker_format,
                        onClose : function (date) {
                            self.$emit("input", date)
                        }
                    })
                }
            });
        }).then(function (value) {
            if (ILTView.sessions.length !== 0) {
                ILTView.sessionHelper = "Choose your session"
            } else {
                ILTView.sessionHelper = "No session available"
            }

        });
    }

    function successAccommodationValidate(resp) {
        resp.json().then(function (data) {
            ILTView.accommodation_list = data.accommodation_list;
            ILTView.all_list = data.all_list;
            ILTView.checkbox_select_all_requests = false;
            $(".accommodation-confirm").notify(gettext("Saved Successfully"), {position: "right", className: "success"});
        })
    }

    function successUpdateILT(resp, index, updateMsg) {
        resp.json().then(function (data) {
            ILTView.sessions = data.sessions;
            ILTView.enrollment = data.enrollment;
            ILTView.isStaff = data.is_staff;
            ILTView.dropdown_list = data.dropdown_list;
            ILTView.accommodation_list = data.accommodation_list;
            ILTView.all_list = data.all_list;
            ILTView.checkbox_select_all_requests = false;
            updateMsg && (ILTView.saveMsg = "succeed");
            console.log('before');
            console.log(ILTView.editSessions[index]);

            for (let i in ILTView.dropdown_list) {
                if (!ILTView.dropdown_list[i][1].includes("expire-for-student")) {
                    ILTView.hide_list_to_student = false;
                    ILTView.hide_list_to_accommodation_admin = false;
                    break
                }
                ILTView.hide_list_to_student = true;
                ILTView.hide_list_to_accommodation_admin = true;
            }

            for (let i in ILTView.dropdown_list) {
                if (!ILTView.dropdown_list[i][1].includes("expire-for-admin")) {
                    ILTView.hide_list_to_admin = false;
                    break
                }
                ILTView.hide_list_to_admin = true
            }

            if (data.enrollment) {
                for (var i = 0; i < ILTView.sessions.length; i++) {
                    if (ILTView.sessions[i][0] === data.enrollment[0]) {
                        ILTView.selectedSession = i;
                        break;
                    }
                }
            } else {
                ILTView.selectedSession = null;
            }
            if (index != null) {
                var x = data.sessions.map(function (item) {
                    var nitem = item.slice();
                    var start_at = nitem[1]['start_at'].split("T");
                    var end_at = nitem[1]['end_at'].split("T");
                    nitem[1]['start_at_date'] = moment(start_at[0]).format(ILTView.date_convert_format);
                    nitem[1]['start_at_time'] = start_at[1];
                    nitem[1]['end_at_date'] = moment(end_at[0]).format(ILTView.date_convert_format);
                    nitem[1]['end_at_time'] = end_at[1];
                        return nitem
                    });
                ILTView.editSessions[index] = x[data.index];
            }
            console.log('after');
            console.log(ILTView.editSessions[index]);
        }).then(function (value) {
            if (ILTView.sessions.length !== 0) {
                ILTView.sessionHelper = "Choose your session"
            } else {
                ILTView.sessionHelper = "No session available"
            }

        });
    }

    function successDelILT(resp, updateMsg) {
        resp.json().then(function (data) {
            ILTView.sessions = data.sessions;
            ILTView.enrollment = data.enrollment;
            ILTView.isStaff = data.is_staff;
            ILTView.dropdown_list = data.dropdown_list;
            ILTView.accommodation_list = data.accommodation_list;
            ILTView.all_list = data.all_list;
            ILTView.checkbox_select_all_requests = false;
            updateMsg && (ILTView.saveMsg = "succeed");

            for (let i in ILTView.dropdown_list) {
                if (!ILTView.dropdown_list[i][1].includes("expire-for-student")) {
                    ILTView.hide_list_to_student = false;
                    ILTView.hide_list_to_accommodation_admin = false;
                    break
                }
                ILTView.hide_list_to_student = true;
                ILTView.hide_list_to_accommodation_admin = true;
            }

            for (let i in ILTView.dropdown_list) {
                if (!ILTView.dropdown_list[i][1].includes("expire-for-admin")) {
                    ILTView.hide_list_to_admin = false;
                    break
                }

                ILTView.hide_list_to_admin = true
            }

            if (data.enrollment) {
                for (var i = 0; i < ILTView.sessions.length; i++) {
                    if (ILTView.sessions[i][0] === data.enrollment[0]) {
                        ILTView.selectedSession = i;
                        break;
                    }
                }
            } else {
                ILTView.selectedSession = null;
            }
            $(".ilt-confirm-del").notify(gettext("Saved Successfully"), {position: "top", className: "success"});
            setTimeout(function () {
                $("#ilt-del-confirm").hide();
                $(".ilt-del-overlay").hide()
            }, 1500)
        }).then(function (value) {
            if (ILTView.sessions.length !== 0) {
                ILTView.sessionHelper = "Choose your session"
            } else {
                ILTView.sessionHelper = "No session available"
            }

        });
    }

    function getILT() {
        Vue.http.get(handlerUrl).then(function (resp) {
            successGetILT(resp, false);
        });
    }

    const ILTView = new Vue({
        el: "#" + init_args['view_id'],
        data: {
            title: "",
            description: "",
            deadline: 0,
            sessions: [],
            editSessions: [],
            sessionHelper: "",
            selectedSession: null,
            admin_selection: null,
            accommodation_admin_selection: null,
            enrollment_admin_selection: null,
            class_admin_selection: null,
            csvFile: null,
            enrollment: [null, {status: null, accommodation: null, comment: "", number_of_one_way: 1, number_of_return: 1}],
            isStaff: false,
            isAdmin: false,
            identifiers: "",
            timezones: [],
            saveMsg: "",
            optional_fields: [],
            dropdown_list: [],
            removedIndex: null,
            date_format: "",
            accommodation_enabled: false,
            accommodation_list: null,
            all_list: null,
            show_unenroll_button: true,
            course_id: "",
            usage_id: "",
            date_convert_format: "YYYY-MM-DD",
            hide_list_to_student: true,
            hide_list_to_admin: true,
            hide_list_to_accommodation_admin: true,
            disable_enroll_button: false,
            enroll_button_title: "",
            bypass_validation_flag: "hidden",
            bypass_validation: false,
            checkbox_select_all_requests: false,
            request_action: "",
            cached_requests: null,
            edited_requests: {},
            previous_enrollment_admin_selection: null,
            change_to_session: null,
            enrollment_tab_confirm_info: "",
            domain: null,
            show_ilt_invitation: true,
            notifyByEmail: true,
        },
        computed: {
            currentSession: function () {
                var sess = JSON.parse(JSON.stringify(this.sessions[this.selectedSession][1])),
                    start_at = sess['start_at'],
                    end_at = sess['end_at'];
                sess['start_at'] = moment(start_at).format(this.date_format);
                sess['end_at'] = moment(end_at).format(this.date_format);
                if (moment(start_at).diff(moment(), 'days') >= this.deadline) {
                    if (sess['available_seats'] > 0) {
                        this.disable_enroll_button = false
                    }
                    else {
                        this.enroll_button_title = gettext("This session is full");
                        this.disable_enroll_button = true
                    }
                }
                else {
                    this.enroll_button_title = gettext("This session is no longer open to registration. Please choose another session.");
                    this.disable_enroll_button = true
                }
                console.log(this.selectedSession);
                return sess
            },
            currentAccommodationList: function () {
                if (this.accommodation_admin_selection != null && this.sessions.length > 0) {
                    var sess_key = this.sessions[this.accommodation_admin_selection][0];
                    return this.accommodation_list[sess_key]
                }
                else {
                    return []
                }
            },
            currentAll_list: function () {
                this.checkbox_select_all_requests = false;
                if (this.enrollment_admin_selection != null && this.sessions.length > 0) {
                    var sess_key = this.sessions[this.enrollment_admin_selection][0];
                    return this.all_list[sess_key]
                }
                else {
                    return []
                }
            },
            currentAll_list_has_user_selected: function () {
                var current_list = this.currentAll_list;
                for (var i in current_list) {
                    if (current_list[i].checked) {
                        return true
                    }
                }
                return false
            },
            ack_attendance_sheet: function () {
                if (this.class_admin_selection != null && this.sessions.length > 0) {
                    var sess = this.sessions[this.class_admin_selection][1],
                        sess_key = this.sessions[this.class_admin_selection][0];
                    if (sess['ack_attendance_sheet']) {
                        return sess['ack_attendance_sheet']
                    }
                    else {
                        return false
                    }
                }
                else {
                    return false
                }
            },

            attendance_sheet_url: function () {
                if (this.class_admin_selection != null && this.sessions.length > 0) {
                    var sess_key = this.sessions[this.class_admin_selection][0],
                        url = "/ilt-attendance-sheet/" + this.course_id + "/" + this.usage_id + "/" + sess_key + "/";
                    return url
                }
                else {
                    return ""
                }
            }
        },
        methods: {
            alertChooseSession: function(event) {
                event.preventDefault();
                LearningTribes.dialog.show("Please choose a session first");
                return false
            },
            showSave: function(sess_id) {
                var x = "#" + sess_id;
                $(x).show();
                console.log("show");
                console.log(this.editSessions[sess_id][1]['duration'])
            },
            accommodationValidate: function() {
                if (this.accommodation_admin_selection != null) {
                    var sess_key = this.sessions[this.accommodation_admin_selection][0],
                        data = this.accommodation_list[sess_key];
                    Vue.http.post(accommodationUrl, {
                        session: sess_key,
                        validation: data
                    }).then(function (resp) {
                        successAccommodationValidate(resp);
                    }, function (resp) {
                        var msg = JSON.parse(resp.bodyText)['error'];
                        $("#" + index).notify(msg, {position: "left"})
                    });
                }
            },
            addSession: function () {
                var now = new Date(),
                    fields = {
                        start_at_date: moment(now.today()).format(this.date_convert_format),
                        start_at_time: now.timeNow(),
                        end_at_date: moment(now.today()).format(this.date_convert_format),
                        end_at_time: now.timeNow(),
                        location: '',
                        total_seats: 0,
                        timezone: ""
                    };
                for (var n = 0; n < this.optional_fields.length; n++) {
                    if (this.optional_fields[n] == 'duration') {
                        fields['duration'] = 0
                    }
                    else {
                        fields[this.optional_fields[n]] = ''
                    }
                }
                this.editSessions.push(["", fields]);
            },
            setRemoveIndex: function (idx) {
                this.removedIndex = idx;
                $("#ilt-del-confirm").show();
                $(".ilt-del-overlay").show()
            },
            delSession: function () {
                var key = this.editSessions.splice(this.removedIndex, 1)[0][0];

                Vue.http.post(delSessionUrl, {
                    sess_key: key
                }).then(successDelILT, errorGetILT)
            },
            cancelDelSession: function () {
                $("#ilt-del-confirm").hide();
                $(".ilt-del-overlay").hide()
            },
            saveSession: function (index) {
                console.log(666);
                console.log(this.editSessions[index][1]['duration']);
                var session = this.editSessions[index],
                    session_copy = JSON.parse(JSON.stringify(session));
                session_copy[1]['start_at'] = [moment(session_copy[1]['start_at_date'], this.date_convert_format).format("YYYY-MM-DD"), session_copy[1]['start_at_time']].join('T');
                session_copy[1]['end_at'] = [moment(session_copy[1]['end_at_date'], this.date_convert_format).format("YYYY-MM-DD"), session_copy[1]['end_at_time']].join('T');
                delete session_copy[1]['start_at_date'];
                delete session_copy[1]['start_at_time'];
                delete session_copy[1]['end_at_date'];
                delete session_copy[1]['end_at_time'];
                if ('duration' in session_copy[1]) {
                    session_copy['1']['duration'] = parseFloat(session_copy['1']['duration']);
                }
                session_copy['1']['total_seats'] = parseFloat(session_copy['1']['total_seats']);
                delete session_copy[1]['available_seats'];
                delete session_copy[1]['timezone_offset'];
                console.log("copy");
                console.log(session_copy);

                Vue.http.post(addSessionUrl, {
                    session: session_copy
                }).then(function (resp) {
                    successUpdateILT(resp, index, true);
                    $("#" + index).notify(gettext("Saved Successfully"), {position: "left", className: "success"}).hide();
                }, function (resp) {
                    var msg = JSON.parse(resp.bodyText)['error'];
                    $("#" + index).notify(msg, {position: "left"})
                });
            },
            updateAckAttendance: function (sess_key, status) {
                Vue.http.post(updateAckUrl, {
                    sess_key: sess_key,
                    status: status
                })
            },
            sessionString: function (start_at, end_at) {
                const start_dt = start_at.split('T');
                const end_dt = end_at.split('T');
                var sessStr = start_dt.join(' ') + "  ";
                if (start_dt[0] === end_dt[0]) {
                    sessStr += end_dt[1];
                } else {
                    sessStr += end_dt.join(" ");
                }
                return sessStr;
            },
            isDatePassNow: function(dt){
                return Date.parse(dt) < Date.now()
            },
            downloadInvitation: function (sessionId) {
                if (this.selectedSession == null) return;
                const enrolledSession = this.sessions.find(f => f[0] == sessionId)
                if(enrolledSession){
                    window.location.href = '/download_invitation/' + this.usage_id + '/' + this.enrollment[0] + '/';
                }      
                
            },
            toggleEnrollment: function () {
                if (this.selectedSession == null) return;
                const sess = this.sessions[this.selectedSession],
                      request_info = this.enrollment[1];
                if (request_info['accommodation'] == null && this.accommodation_enabled) {
                    LearningTribes.dialog.show(gettext("Please choose the accommodation need"));
                    return
                }
                Vue.http.post(enrollmentUrl, {session: sess[0], request_info: request_info}).then(function (resp) {
                    resp.json().then(function (value) {
                        ILTView.sessions = value['sessions'];
                        ILTView.enrollment = value['enrollment'];
                        ILTView.accommodation_list = value.accommodation_list;
                        ILTView.all_list = value.all_list;
                        ILTView.checkbox_select_all_requests = false;
                        if (ILTView.enrollment[0] != null) {
                            for (var i = 0; i < ILTView.sessions.length; i++) {
                                if (ILTView.sessions[i][0] === ILTView.enrollment[0]) {
                                    ILTView.selectedSession = i;
                                    break;
                                }
                            }
                        } else {
                            ILTView.selectedSession = null;
                        }
                    })
                })
            },
            batchToggleEnrollment: function (handlerUrl) {
                if (this.enrollment_admin_selection == null) {
                    LearningTribes.dialog.show('choose a session first');
                    return
                }
                var users = '';
                if (handlerUrl === batchUnenrollUrl) {
                    var result = [],
                        // current_list = this.currentAcceptedConfirmed_list;
                        current_list = this.currentAll_list;
                    current_list.forEach(function (ele) {
                        if (ele.checked) {
                            result.push(ele.employee_id)
                        }
                    });
                    users = result.join();
                    console.log(users)
                }
                else {
                    users = this.identifiers
                }
                if (users === '') return;
                const sess = this.sessions[this.enrollment_admin_selection];
                Vue.http.post(handlerUrl, {
                    identifiers: users,
                    session: sess[0],
                    bypass_validation: this.bypass_validation,
                    notify_by_email: this.notifyByEmail
                }).then(function (resp) {
                    resp.json().then(function (value) {
                        ILTView.sessions = value['data']['sessions'];
                        ILTView.enrollment = value['data']['enrollment'];
                        ILTView.accommodation_list = value['data']['accommodation_list'];
                        ILTView.all_list = value['data']['all_list'];
                        ILTView.checkbox_select_all_requests = false;
                        if (ILTView.enrollment) {
                            for (var i = 0; i < ILTView.sessions.length; i++) {
                                if (ILTView.sessions[i][0] === ILTView.enrollment[0]) {
                                    ILTView.selectedSession = i;
                                    break;
                                }
                            }
                        } else {
                            ILTView.selectedSession = null;
                        }
                        console.log(value['result']);
                        var resultMessage = jsonToStr(value['result'])
                        LearningTribes.dialog.show(resultMessage)
                    })
                })
            },
            batchEnroll: function () {
                this.batchToggleEnrollment(batchEnrollUrl)
            },
            show_unenroll_confirm: function () {
                $("#unenroll-confirm").show();
                $(".ilt-unenroll-overlay").show()
            },
            cancel_unenroll: function () {
                $("#unenroll-confirm").hide();
                $(".ilt-unenroll-overlay").hide();
                this.unselect_all();
                this.request_action = '';
            },
            batchUnenroll: function () {
                $("#unenroll-confirm").hide();
                $(".ilt-unenroll-overlay").hide();
                this.batchToggleEnrollment(batchUnenrollUrl);
                $(".actions li").removeClass('active');
                this.request_action = '';
                ILTView.unselect_all();
                ILTView.enrollment_tab_confirm_info = "unenroll"
            },
            getSession: function (sessionHash) {
                if (!sessionHash) return null;
                for (var i = 0; i < this.sessions.length; i++) {
                    if (this.sessions[i][0] === sessionHash) {
                        return this.sessions[i][1]
                    }
                }
            },
            teacherTimeToLocal: function (teacherTime, offsetHours) {
                teacherTime += teacherTime.toUpperCase().endsWith('Z') ? '' : 'Z';
                var dateObj = new Date(teacherTime);
                dateObj.addHours(-offsetHours);
                return dateObj.toISOString();
            },
            addToCalendar: function (session_id) {
                var cal = ics();
                var session = this.getSession(session_id);
                if (session === null) return;
                var uid = this.usage_id + "_" + session_id;
                cal.addEvent(uid, this.title, this.description, session['location'],
                    this.teacherTimeToLocal(session['start_at'], session['timezone_offset']),
                    this.teacherTimeToLocal(session['end_at'], session['timezone_offset']));
                cal.download()
            },
            downloadCSV: function () {
                Vue.http.get(enrolledUsersUrl, {params: {session: this.sessions[this.class_admin_selection][0]}}).then(function (resp) {
                    resp.json().then(function (value) {

                        var csv = Papa.unparse(value);
                        if (detectIE()) {
                            var csvData = decodeURIComponent(csv);
                            if (window.navigator.msSaveBlob) {
                                var blob = new Blob([csvData], {type: "application/csv;charset=utf-8;"});
                                window.navigator.msSaveBlob(blob, ILTView.dropdown_list[ILTView.class_admin_selection][0] + '.csv');
                            }
                        }
                        else {
                            var uri = 'data:text/csv;charset=utf-8,' + escape(csv);
                            var link = document.createElement("a");
                            link.href = uri;
                            link.style = "visibility:hidden";
                            link.download = ILTView.dropdown_list[ILTView.class_admin_selection][0] + '.csv';
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                        }

                    });
                })
            },
            onCSVChange: function (e) {
                var files = e.target.files || e.dataTransfer.files;
                if (!files.length) return;
                this.csvFile = files[0];
            },
            validateCSV: function () {
                if (this.csvFile) {
                    const _this = this;
                    Papa.parse(_this.csvFile, {
                        skipEmptyLines: true,
                        header: true,
                        complete: function (results, f) {
                            var uploadJson = {};
                            for (var i = 0; i < results.data.length; i++) {
                                var row = results.data[i];
                                if (row['attendance']) {
                                    uploadJson[row['username']] = row['attendance'];
                                }
                            }
                            console.log(uploadJson);
                            Vue.http.post(gradeUrl, uploadJson).then(function (value) {
                                LearningTribes.dialog.show('grade success')
                            });
                        }
                    })
                }
            },

            select_all: function () {
                // var current_list = this.currentAcceptedConfirmed_list;
                var current_list = this.currentAll_list;
                this.checkbox_select_all_requests = !this.checkbox_select_all_requests;
                for (var i in current_list) {
                    current_list[i].checked = this.checkbox_select_all_requests;
                }
            },

            unselect_all: function () {
                // var current_list = this.currentAcceptedConfirmed_list;
                var current_list = this.currentAll_list;
                this.checkbox_select_all_requests = false;
                for (var i in current_list) {
                    current_list[i].checked = false;
                }
            },

            check_request_action: function (action) {
                // var current_list = this.currentAcceptedConfirmed_list;
                var current_list = this.currentAll_list;
                this.previous_enrollment_admin_selection = this.enrollment_admin_selection;
                this.enrollment_tab_confirm_info = "";
                console.log(this.cached_requests);
                if (action === this.request_action) {
                    this.request_action = '';
                    $(".actions li").removeClass('active');
                    if (action === 'edit') {
                        this.cancel_update_accepted_requests()
                    }
                    if (action === 'accept') {
                        this.cancel_accept()
                    }
                    if (action === 'unenroll') {
                        this.cancel_unenroll()
                    }
                    if (action === 'change_session') {
                        this.cancel_change_session()
                    }
                    return
                }
                if (action === 'edit') {
                    this.request_action = 'edit';
                    this.cached_requests = JSON.stringify(current_list);
                    $(".column-action-checkbox").hide();
                    $(".actions li").removeClass('active');
                    $(".edit-action").addClass('active');
                }
                else {
                    if (this.cached_requests != null && this.cached_requests != JSON.stringify(current_list) && this.request_action === 'edit') {
                        LearningTribes.dialog.show("Please save or cancel the changes first");
                    }
                    else {
                        this.request_action = action;
                        $(".actions li").removeClass('active');
                        if (action === 'unenroll') {
                            $(".unenroll-action").addClass('active')
                        } else if (action === 'change_session') {
                            $(".change-action").addClass('active')
                        } else {
                            $(".accept-action").addClass('active')
                        }
                        $(".column-action-checkbox").show()
                    }
                }
            },

            enrollment_admin_selection_check: function () {
                if (this.request_action === 'edit') {
                    LearningTribes.dialog.show("Please save or cancel the changes first");
                    this.enrollment_admin_selection = this.previous_enrollment_admin_selection;
                }
                else {
                    this.previous_enrollment_admin_selection = this.enrollment_admin_selection;
                }
            },

            update_edited_requests: function(index, user_id) {
                // this.edited_requests[user_id] = this.currentAcceptedConfirmed_list[index];
                this.edited_requests[user_id] = this.currentAll_list[index];
                console.log(this.edited_requests)
            },

            batch_update_accepted_requests: function () {
                var sess = this.sessions[this.enrollment_admin_selection];
                Vue.http.post(updateAcceptedRequestUrl, {
                    session: sess[0],
                    learner_requests: this.edited_requests
                }).then(function (resp) {
                    resp.json().then(function (value) {
                        ILTView.enrollment = value['enrollment'];
                        ILTView.accommodation_list = value.accommodation_list;
                        ILTView.all_list = value.all_list;
                        ILTView.checkbox_select_all_requests = false;
                        ILTView.edited_requests = {};
                        ILTView.request_action = '';
                        ILTView.cached_requests = null;
                        $(".column-action-checkbox").show();
                        $(".actions li").removeClass('active');
                        ILTView.unselect_all();
                        ILTView.enrollment_tab_confirm_info = "edit"
                    })
                })
            },

            batch_switch_session: function () {
                var result = [],
                    // current_list = this.currentAcceptedConfirmed_list;
                    current_list = this.currentAll_list;
                current_list.forEach(function (ele) {
                    if (ele.checked) {
                        result.push(ele.user_id)
                    }
                });
                var sess = this.sessions[this.enrollment_admin_selection];
                Vue.http.post(switchSessionUrl, {
                    old_session: sess[0],
                    new_session: this.change_to_session,
                    learners: result,
                }).then(function (resp) {
                    resp.json().then(function (value) {
                        ILTView.enrollment = value['enrollment'];
                        ILTView.accommodation_list = value.accommodation_list;
                        ILTView.all_list = value.all_list;
                        ILTView.checkbox_select_all_requests = false;
                        ILTView.edited_requests = {};
                        ILTView.request_action = '';
                        ILTView.cached_requests = null;
                        ILTView.unselect_all();
                        $(".actions li").removeClass('active');
                        ILTView.enrollment_tab_confirm_info = "change_session"
                    })
                })
            },

            batch_accept_requests: function () {
                var requests = {},
                    current_list = this.currentAll_list;
                current_list.forEach(function (ele) {
                    if (ele.checked) {
                        requests[ele.user_id] = ele
                    }
                });
                var sess = this.sessions[this.enrollment_admin_selection];
                Vue.http.post(acceptRequestUrl, {
                    session: sess[0],
                    learner_requests: requests
                }).then(function (resp) {
                    resp.json().then(function (value) {
                        ILTView.enrollment = value['enrollment'];
                        ILTView.accommodation_list = value.accommodation_list;
                        ILTView.all_list = value.all_list;
                        ILTView.checkbox_select_all_requests = false;
                        ILTView.edited_requests = {};
                        ILTView.request_action = '';
                        ILTView.cached_requests = null;
                        $(".actions li").removeClass('active');
                        ILTView.unselect_all();
                        ILTView.enrollment_tab_confirm_info = "accept"
                    })
                })
            },

            cancel_update_accepted_requests: function () {
                this.edited_requests = {};
                this.request_action = '';
                var sess_key = this.sessions[this.enrollment_admin_selection][0];
                this.all_list[sess_key] = JSON.parse(this.cached_requests);
                this.cached_requests = null;
                $(".column-action-checkbox").show();
                $(".actions li").removeClass('active');
                ILTView.unselect_all();
            },

            cancel_accept: function () {
                this.unselect_all();
                this.request_action = '';
            },

            trans: function (text) {
                return gettext(text)
            },

            is_url_location: function (location) {
                // if location is a URL, then convert it to <a>location</a>
                var regexp = /(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/;
                return regexp.test(location)
            },

            onNotifyByEmailChange(e) {
                console.log('onNotifyByEmailChange ', e, this.notifyByEmail)
            }
        }
    });
    getILT();
}

//# sourceURL=ilt.js
