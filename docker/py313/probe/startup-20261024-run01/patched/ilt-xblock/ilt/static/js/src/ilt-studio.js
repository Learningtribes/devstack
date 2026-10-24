function ILTXBlockStudio(runtime, element) {
    require(['vue', 'vue-resource'], function (Vue, resource) {
        Vue.use(resource);
        $(function ($) {
            var handlerUrl = runtime.handlerUrl(element, 'studio_handler');
            var ILTStudioView;

            Vue.http.interceptors.push(function (request, next) {
                if (request.method === 'POST') {
                    request.headers.set('X-CSRFToken', $.cookie('csrftoken'));
                }
                next();
            });
            Vue.component('datepicker', {
                template: '<input v-bind:value="value">',
                props: ['value'],
                mounted: function () {
                    var self = this;
                    $(self.$el).datepicker({
                        dateFormat: 'yy-mm-dd',
                        onSelect: function (date) {
                            self.$emit("input", date)
                        }
                    })
                }
            });

            Vue.component('timepicker', {
                template: '<input v-bind:value="value">',
                props: ['value'],
                mounted: function () {
                    var self = this;
                    $(self.$el).timepicker({
                        timeFormat: 'H:i'
                    });
                    $(this.$el).on('changeTime', function (e) {
                        self.$emit("input", e.target.value);
                    });
                }
            });

            function datetimepicker() {
                Vue.nextTick(function () {
                    $('.datepicker').datepicker({dateFormat: 'yy-mm-dd'});
                    $('.timepicker').timepicker({timeFormat: 'H:i'});
                });
            }

            function successGetILT(data) {
                ILTStudioView.title = data.title;
                ILTStudioView.description = data.description;
                ILTStudioView.weight = data.weight;
                ILTStudioView.sessions = data.sessions.map(function (item) {
                    var nitem = item.slice();
                    var start_at = nitem[1]['start_at'].split("T");
                    var end_at = nitem[1]['end_at'].split("T");
                    nitem[1]['start_at_date'] = start_at[0];
                    nitem[1]['start_at_time'] = start_at[1];
                    nitem[1]['end_at_date'] = end_at[0];
                    nitem[1]['end_at_time'] = end_at[1];
                    return nitem
                });
                ILTStudioView.isStaff = data.is_staff;
                ILTStudioView.timezones = data.timezones;
            }

            function getILT() {
                Vue.http.get(handlerUrl).then(function (resp) {
                    resp.json().then(successGetILT);
                });
            }

            ILTStudioView = new Vue({
                el: ".ilt-xblock-studio",
                data: {
                    title: "",
                    description: "",
                    weight: 0,
                    sessions: [],
                    isStaff: false,
                    timezones: [],
                },
                methods: {
                    addNewSession: function () {
                        this.sessions.push(["", {
                            start_at: "",
                            end_at: "",
                            start_at_date: "",
                            start_at_time: "",
                            end_at_date: "",
                            end_at_time: "",
                            instructor: '',
                            location: '',
                            total_seats: 0,
                            timezone: ""
                        }]);
                    },
                    saveILT: function () {
                        var sessions = this.sessions.map(function (item) {
                            var nitem = item.slice();
                            nitem[1]['start_at'] = [nitem[1]['start_at_date'], nitem[1]['start_at_time']].join('T');
                            nitem[1]['end_at'] = [nitem[1]['end_at_date'], nitem[1]['end_at_time']].join('T');
                            delete nitem[1]['start_at_date'];
                            delete nitem[1]['start_at_time'];
                            delete nitem[1]['end_at_date'];
                            delete nitem[1]['end_at_time'];

                            nitem['1']['total_seats'] = parseInt(nitem['1']['total_seats']);
                            return nitem
                        });
                        runtime.notify('save', {state: 'start'});

                        Vue.http.post(handlerUrl, {
                            sessions: sessions,
                            description: this.description,
                            title: this.title,
                            weight: this.weight,
                        }).then(function (resp) {
                            // resp.json().then(successGetILT);
                            // location.reload();
                            runtime.notify('save', {state: 'end'});

                        })
                    },
                    cancelILT: function () {
                        runtime.notify('cancel', {});
                    }
                }
            });
            getILT();
            window.ILTStudioView = ILTStudioView;
        });
    });

}
