# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import functools
import logging
import json
import os
import string
import time
import uuid
import re
import pytz
import random
import pkg_resources

from copy import deepcopy
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pytz import UnknownTimeZoneError

from jsonschema import Draft4Validator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import MultipleObjectsReturned
from django.urls import reverse

from xblock.scorable import Score
from xblock.core import XBlock
from xblock.exceptions import JsonHandlerError
from xblock.fields import Scope, String, Float, Dict, Boolean, Integer
from xblock.fragment import Fragment
from xblock.validation import ValidationMessage

from instructor.enrollment_email import send_mail_to_student
from student.enrollment import get_user_email_language
from student.models import CourseEnrollment
from student.roles import CourseInstructorRole, CourseStaffRole
from lms.djangoapps.instructor.views.tools import get_student_from_identifier
from openedx.core.djangoapps.site_configuration import helpers as configuration_helper
from xmodule.modulestore.django import modulestore

from mako.template import Template
from webob import Response

from xblockutils.studio_editable import StudioEditableXBlockMixin

from .mixins import ScorableXBlockMixin


User = get_user_model()
_ = lambda text: text

ILT_DEFAULT_FIELDS = ['end_at', 'start_at', 'location', 'timezone', 'total_seats']

# create logger
logger = logging.getLogger("edx.xblock.ilt")

d = '/edx/var/log/lms/ilt_xblock.log'
if os.path.exists(d) and os.access(d, os.W_OK) or not os.path.exists(d):
    log_handler = TimedRotatingFileHandler("/edx/var/log/lms/ilt_xblock.log",
                                           when="W0",
                                           backupCount=5,
                                           encoding="utf-8")

    log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
    log_formatter.converter = time.gmtime
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)


def _split_input_list(str_list):
    """
    Separate out individual student email from the comma, or space separated string.

    e.g.
    in: "Lorem@ipsum.dolor, sit@amet.consectetur\nadipiscing@elit.Aenean\r convallis@at.lacus\r, ut@lacinia.Sed"
    out: ['Lorem@ipsum.dolor', 'sit@amet.consectetur', 'adipiscing@elit.Aenean', 'convallis@at.lacus', 'ut@lacinia.Sed']

    `str_list` is a string coming from an input text area
    returns a list of separated values
    """

    new_list = re.split(r'[\n\r\s,]', str_list)
    new_list = [s.strip() for s in new_list]
    new_list = [s for s in new_list if s != '']

    return new_list


def get_timezone_offset(tz):
    return int(datetime.now(pytz.timezone(tz)).utcoffset().total_seconds() / 3600)


def get_timezones():
    custom_timezones = configuration_helper.get_value("ILT_TIMEZONE_LIST", [])
    if custom_timezones:
        custom_timezones.sort()
        timezones = [tz for tz in custom_timezones if tz in pytz.common_timezones]
    else:
        timezones = pytz.common_timezones
    return [(tz, get_timezone_offset(tz)) for tz in timezones]


def sorted_sessions(sessions):
    items = sessions.items()
    for k, v in items:
        if k == 'counter':
            items.remove((k, v))
            break
    items.sort(key=lambda itm: decode_datetime(itm[1]['start_at']))
    return items


def generate_key_for_session():
    return uuid.uuid4().hex
    # return sha1(json.dumps(sorted(session.items()))).hexdigest()


def get_html(path, data):
    tplt = Template(pkg_resources.resource_string(__name__, path))
    return tplt.render_unicode(**data)


def json_handler(staff_only=False, *methods):
    def handler(func):
        """
        Wrap a handler to consume and produce JSON.

        Rather than a Request object, the method will now be passed the
        JSON-decoded body of the request. The request should be a POST request
        in order to use this method. Any data returned by the function
        will be JSON-encoded and returned as the response.

        The wrapped function can raise JsonHandlerError to return an error
        response with a non-200 status code.

        This decorator will return a 405 HTTP status code if the method is not
        POST.
        This decorator will return a 400 status code if the body contains
        invalid JSON.
        """

        @XBlock.handler
        @functools.wraps(func)
        def wrapper(self, request, suffix=''):
            if staff_only and not self.is_current_user_staff():
                return JsonHandlerError(401, "Unauthorized, Staff only").get_response(allow=methods)
            """The wrapper function `json_handler` returns."""
            if request.method not in methods:
                return JsonHandlerError(405, "Method not allowed").get_response(allow=methods)
            if request.method == "POST":
                try:
                    request_json = json.loads(request.body)
                except ValueError:
                    return JsonHandlerError(400, "Invalid JSON").get_response()
            elif request.method == 'GET':
                request_json = None
            else:
                return JsonHandlerError(405, "Method not allowed").get_response(allow=methods)

            try:
                response = func(self, request, request_json, suffix)
            except JsonHandlerError as err:
                return err.get_response()

            if isinstance(response, Response):
                return response
            else:
                return Response(json.dumps(response), content_type='application/json', charset='utf8')

        return wrapper

    return handler


def resource_string(path):
    """Handy helper for getting resources from our kit."""

    data = pkg_resources.resource_string(__name__, path)
    return data.decode("utf8")


DT_FORMAT = '%Y-%m-%dT%H:%M'
# DT_FORMAT = '%d-%m-%YT%H:%M'


def decode_datetime(dts):
    return datetime.strptime(dts, DT_FORMAT)


def convert_datetime(date_str, date_format=None):
    if not date_format:
        date_format = configuration_helper.get_value("ILT_DATE_FORMAT", "YYYY-MM-DD HH:mm")
    date_format = date_format.replace("YYYY", "%Y").replace("DD", "%d").replace(
        "MM", "%m"
    ).replace("HH", "%H").replace("mm", "%M")

    return decode_datetime(date_str).strftime(date_format)


json_validator = Draft4Validator({
            'type': 'object',
            'required': ['end_at', 'start_at', 'location', 'timezone', 'total_seats'],
            'properties': {
                'end_at': {
                    'type': 'string',
                    'pattern': '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$'
                },
                'start_at': {
                    'type': 'string',
                    'pattern': '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$'
                },
                'instructor': {
                    'type': 'string',
                },
                'location': {
                    'type': 'string',
                },
                'timezone': {
                    'enum': [zone[0] for zone in get_timezones()] + [""],
                },
                'total_seats': {
                    'type': 'integer',
                    'minimum': 0,
                },
                'duration': {
                    'type': 'number',
                    'minimum': 0,
                },
                'area_region': {
                    'type': 'string',
                },
                'address': {
                    'type': 'string',
                },
                'zip_code': {
                    'type': 'string',
                },
                'city': {
                    'type': 'string',
                },
                'location_id': {
                    'type': 'string',
                },
                'ack_attendance_sheet': {
                    'type': 'boolean',
                }
            },
            "additionalProperties": False,
        })


@XBlock.needs('user', 'i18n', 'request')
class ILTXBlock(StudioEditableXBlockMixin, ScorableXBlockMixin, XBlock):
    display_name = String(
        default=_("Instructor Led Training"),
        sessions=Scope.settings,
        enforce_type=True,
        display_name=_("Display Name"),
        help=_("Display name for this module"),
    )

    deadline = Integer(
        default=None,
        scope=Scope.settings,
        display_name=_("Registration Deadline"),
        help=_("The enroll button will be disabled for sessions that start in less than X days."),
        required=True
    )

    has_score = Boolean(
        default=True,
        scope=Scope.settings,
        enforce_type=True,
        display_name=_('Score'),
        help=_("Does this scorm, need to be scored?")
    )

    icon_class = String(
        default='problem',
        scope=Scope.settings,
        values=("problem", "video", "other"),
        enforce_type=True,
        display_name=_("Icon"),
        help=_("Icon be used in course page")
    )

    weight = Float(
        default=1.0,
        scope=Scope.settings,
        values={"min": 0, "step": 0.1},
        enforce_type=True,
        display_name=_('Weight'),
        help=_('Relative weight in this course section')
    )

    description = String(
        default="", scope=Scope.settings,
        display_name=_("Description"),
        help=_('Enter a class description.')
    )

    sessions = Dict(
        default={},
        scope=Scope.user_state_summary,
        display_name=_('Sessions'),
        help=_('You can add one or more sessions. Learners will choose one session to enroll.')

    )

    enrolled_users = Dict(
        default={}, scope=Scope.user_state_summary,
        display_name=''
    )

    ilt_allow_rescore = Boolean(
        default=True,
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Rescore"),
        help=_("Does this module allow rescore features? (instructor set score)")
    )

    ilt_score = Float(
        default=0.0,
        scope=Scope.user_state,
        enforce_type=True,
    )

    editable_fields = ('display_name', 'deadline', 'has_score', 'icon_class', 'weight', 'description')

    # region Runtime functions

    def max_score(self):
        return 1.0

    def allows_rescore(self):
        return self.ilt_allow_rescore

    def set_score(self, score):
        self.ilt_score = self.max_score() * score.raw_earned / score.raw_possible

    def get_score(self):
        return Score(raw_possible=self.max_score(), raw_earned=self.ilt_score)

    def calculate_score(self):
        return self.get_score()

    def has_submitted_answer(self):
        return self.ilt_score == 0

    def get_progress(self):
        return None

    # endregion

    # region Convention capability region
    # To compatible with old data, use this.
    # when access self fields, always prefix with short name
    # we will remove this after find a way to rename field in database
    @property
    def ilt_sessions(self):
        return self.sessions

    @ilt_sessions.setter
    def ilt_sessions(self, value):
        self.sessions = value

    @property
    def ilt_enrolled_users(self):
        return self.enrolled_users

    @ilt_enrolled_users.setter
    def ilt_enrolled_users(self, val):
        self.enrolled_users = val

    @property
    def ilt_description(self):
        return self.description

    @ilt_description.setter
    def ilt_description(self, val):
        self.description = val

    # endregion

    def get_current_user(self):
        return self.runtime.service(self, 'user')._django_user

    def is_current_user_staff(self):
        user = self.get_current_user()

        course_admins = CourseInstructorRole(self.course_id).users_with_role()
        course_staffs = CourseStaffRole(self.course_id).users_with_role()
        return user.is_staff or user in course_admins or user in course_staffs

    def is_current_user_admin(self):
        user = self.get_current_user()

        course_admins = CourseInstructorRole(self.course_id).users_with_role()
        return user.is_staff or user in course_admins

    # region Helper functions

    def send_group_email(self, request, learners, action, **kwargs):
        supervisors = {}
        hotel_reservation = kwargs.get('hotel_reservation')
        course = modulestore().get_course(self.course_id)

        session_info = deepcopy(kwargs.get("session_info", {}))
        if 'start_at' in session_info and 'end_at' in session_info:
            session_info['start_at'] = convert_datetime(session_info['start_at'])
            session_info['end_at'] = convert_datetime(session_info['end_at'])
        for l in learners:
            email = l.profile.lt_ilt_supervisor
            if email:
                if email in supervisors:
                    supervisors[email].append(l.profile.name)
                else:
                    supervisors[email] = [l.profile.name]

        ilt_link = request.referer
        params = {
            'name': '',
            'ilt_link': ilt_link,
            'ilt_name': self.display_name,
            'site_name': None,
            'hotel_info': hotel_reservation,
            'message': action,
            'action': action,
            'course_name': course.display_name,
            'session_info': session_info
        }

        for k, v in supervisors.items():
            params['learners'] = ', '.join(v)
            send_mail_to_student(k, params, language=get_user_email_language(self.get_current_user()))

        course_admins = CourseInstructorRole(self.course_id).users_with_role()
        if hotel_reservation:
            for u in course_admins:
                params['name'] = u.profile.name or u.username
                params['message'] = 'ilt_hotel_cancel'
                send_mail_to_student(u.email, params, language=get_user_email_language(u))

    def send_email(self, name, user, request, **kwargs):

        session_info = deepcopy(kwargs.get("session_info", {}))
        request_info = deepcopy(kwargs.get("request_info", {}))
        if 'start_at' in session_info and 'end_at' in session_info:
            session_info['start_at'] = convert_datetime(session_info['start_at'])
            session_info['end_at'] = convert_datetime(session_info['end_at'])
        course = modulestore().get_course(self.course_id)
        if name == 'ilt_validate':
            email = user.profile.lt_ilt_supervisor
            ilt_link = reverse("ilt_validation", kwargs={
                "course_id": self.course_id,
                "usage_id": self.location,
                "user_id": user.id
            })
            ilt_link = request.host_url + ilt_link
        elif name == 'ilt_self_unenroll':
            email = user.profile.lt_ilt_supervisor
            ilt_link = request.referer
        else:
            if settings.LEARNER_NO_EMAIL and user.email.endswith(settings.LEARNER_NO_EMAIL):
                email = user.profile.lt_ilt_supervisor
            else:
                email = user.email
            ilt_link = request.referer
        params = {'message': name,
                  'name': user.profile.name,
                  'ilt_link': ilt_link, 'site_name': None,
                  'ilt_name': self.display_name,
                  'course_name': course.display_name,
                  'session_info': session_info,
                  'request_info': request_info}
        print("request_info: ", request_info)
        info = self.get_enrollment(user.id)
        if name == 'ilt_confirmed' or name == 'ilt_hotel_updated':
            hotel = info[1].get('hotel')
            params['hotel'] = hotel

        if email:
            logger.info("email_type: {name}, to user: {user_email}".format(
                name=name, user_email=email
            ))
            send_mail_to_student(email, params,
                                 language=get_user_email_language(self.get_current_user()))

        # case there is hotel reservation
        if name == 'ilt_self_unenroll' and kwargs.get('hotel_info'):
            params['hotel_info'] = [kwargs.get('hotel_info')]
            params['message'] = "ilt_hotel_cancel"
            params['action'] = name
            course_admins = CourseInstructorRole(self.course_id).users_with_role()
            for u in course_admins:
                params['name'] = u.profile.name or u.username
                send_mail_to_student(u.email, params, language=get_user_email_language(u))

    def get_data(self):
        course = modulestore().get_course(self.course_id)
        return {
            "title": self.display_name,
            "course_name": course.display_name,
            "description": self.ilt_description,
            "is_staff": self.is_current_user_staff(),
            "is_admin": self.is_current_user_admin(),
            "deadline": self.deadline,
        }

    def get_studio_data(self):
        data = self.get_data()
        data.update({
            "weight": self.weight,
            "sessions": sorted_sessions(self.sessions),
            "timezones": get_timezones()
        })

        return data

    def validate_field_data(self, validation, data):
        if data.deadline is None:
            validation.add(ValidationMessage(ValidationMessage.ERROR,
                                             self.ugettext("The registration deadline cannot be empty")
                                             ))

    def get_student_data(self):
        data = self.get_data()
        sessions = {}
        user = self.get_current_user()

        # compatibility for enrolled_user data, we change the data format since we
        # design the ILT workflow for Sephora
        # the old data format is "session_id": [user_id, user_id]
        # new data format is "session_id": {user_id: {registration_info}, user_id: {registration_info}}
        for k, v in self.ilt_enrolled_users.items():
            if type(v) == list:
                value = {x: {"status": "confirmed"} for x in v}
                self.ilt_enrolled_users[k] = value

        if len(self.ilt_sessions) == 0:
            self.ilt_sessions['counter'] = 0

        # compatible for old ilt data
        elif 'counter' not in self.ilt_sessions:
            counter = 0
            tmp_sessions = {}
            tmp_enrolled_users = {}
            for k in self.ilt_sessions.keys():
                counter += 1
                tmp_sessions[counter] = self.ilt_sessions[k]
                if k in self.ilt_enrolled_users:
                    tmp_enrolled_users[counter] = self.ilt_enrolled_users[k]
            tmp_sessions['counter'] = counter
            self.ilt_sessions = tmp_sessions
            self.ilt_enrolled_users = tmp_enrolled_users

        for k, v in self.ilt_sessions.items():
            # print(datetime.now() - decode_datetime(v['end_at']), decode_datetime(v['end_at']))

            if k == "counter":
                continue
            #if datetime.now() - decode_datetime(v['end_at']) > timedelta(days=30):
            #    v['expire'] = True
            if 'expire' in v:
                v.pop('expire')   # for old data, it might have 'expire'
            v = self.timezone_offset(v)
            # if decode_datetime(v['start_at']) < now().replace(tzinfo=None) + timedelta(hours=v['timezone_offset']):
            #     continue
            v = self.sess_with_available_seats(k, v.copy())
            sessions[k] = v

        optional_fields = configuration_helper.get_value("ILT_OPTIONAL_FIELDS", [])
        date_format = configuration_helper.get_value("ILT_DATE_FORMAT", "YYYY-MM-DD HH:mm")
        all_list = self.get_all_list()

        data.update({
            'show_unenroll_button': user.profile.lt_ilt_supervisor is None,
            'sessions': sorted_sessions(sessions),
            'timezones': get_timezones(),
            'enrollment': self.get_enrollment(self.runtime.user_id),
            'ilt_optional_fields': optional_fields,
            'dropdown_list': self.get_dropdown_list(sessions),
            'date_format': date_format,
            'accommodation': configuration_helper.get_value("ILT_ACCOMMODATION_ENABLED", False),
            'accommodation_list': all_list[1],
            'all_list': all_list[0],
            'course_id': unicode(self.course_id),
            'usage_id': unicode(self.location),
            'bypass_validation_flag': configuration_helper.get_value("ILT_BYPASS_VALIDATION_WORKFLOW", "hidden"),
            'show_ilt_invitation': configuration_helper.get_value('SHOW_ILT_INVITATION', True)
        })
        return data

    def get_fields_data(self):
        title_field = self.fields['display_name']
        desc_field = self.fields['description']
        weight_field = self.fields['weight']
        sess_field = self.fields['sessions']
        return {
            'title': title_field.display_name, 'title_help': title_field.help,
            'desc': desc_field.display_name, 'desc_help': desc_field.help,
            'weight': weight_field.display_name, 'weight_help': weight_field.help,
            'sess': sess_field.display_name, 'sess_help': sess_field.help,
            '_': self.ugettext,
            'view_id': self.generate_view_id()
        }

    # endregion

    def _check_session_schema(self, istn):
        return json_validator.is_valid(istn)

    @json_handler(True, 'POST')
    def update_ack_attendance(self, request, data, suffix=''):
        sess_key = data['sess_key']
        status = data['status']
        if sess_key in self.ilt_sessions:
            self.ilt_sessions[sess_key]['ack_attendance_sheet'] = status
            logger.info("Updated acknowledge reception of the attendance sheet for "
                        "ilt_module: {usage_key}, session_nb: #{sess_key}, status: {status}, User id: {user_id}".format(
                            usage_key=unicode(self.location), sess_key=sess_key, status=status, user_id=self.runtime.user_id
                        ))
            return self.get_student_data()
        else:
            raise JsonHandlerError(400, "Bad request !")

    @json_handler(True, 'POST')
    def add_session(self, request, data, suffix=''):
        _ = self.ugettext
        session = data['session']
        sess_key = session[0]
        sess = session[1]
        if not self._check_session_schema(sess):
            raise JsonHandlerError(400, "Bad request !")
        for k, v in sess.items():
            if v == "" and k != "location_id":
                raise JsonHandlerError(400, "Empty fields are not allowed !")
        available_seats = self.sess_with_available_seats(sess_key, sess).pop('available_seats')
        if available_seats < 0:
            raise JsonHandlerError(
                400, _("Total seats number cannot be lower than {enrolled}").format(
                    enrolled=sess['total_seats'] - available_seats
                )
            )
        if not sess_key:
            self.ilt_sessions['counter'] = self.ilt_sessions['counter'] + 1
            sess_key = str(self.ilt_sessions['counter'])
        if sess_key in self.ilt_sessions:
            old_sess = self.ilt_sessions[sess_key]
            if old_sess['start_at'] != sess['start_at'] or (old_sess['end_at'] != sess['end_at']):
                user_ids = self.ilt_enrolled_users.get(sess_key, [])
                users = User.objects.filter(id__in=user_ids).only('email')
                for u in users:
                    self.send_email('ilt_session_time_changed', u, request, session_info=sess)
        self.ilt_sessions[sess_key] = sess
        result = self.get_student_data()
        for r in result['sessions']:
            if r[0] == sess_key:
                result['index'] = result['sessions'].index(r)
                break
        logger.info("Updated or created a session, ilt_module: {usage_key}, session_nb: #{sess_key}, "
                   "session_info: {sess}, User: {user_id}".format(
                    usage_key=unicode(self.location),
                    sess_key=sess_key,
                    sess=sess,
                    user_id=self.runtime.user_id
                    ))
        return result

    @json_handler(True, 'POST')
    def del_session(self, request, data, suffix=''):
        sess_key = data['sess_key']
        if sess_key in self.ilt_sessions:
            hotel_reservation = []
            session_info = self.ilt_sessions.pop(sess_key)
            user_ids = self.ilt_enrolled_users.get(sess_key, {})
            users = User.objects.filter(id__in=user_ids)
            for u in users:
                if settings.LEARNER_NO_EMAIL and u.email.endswith(settings.LEARNER_NO_EMAIL):
                    pass
                else:
                    self.send_email('ilt_session_canceled', u, request, session_info=session_info)
                info = self.get_enrollment(u.id, sess_key)
                if info[1].get('hotel', '') != '':
                    hotel_info = "Name: {user_name}, Hotel Booked: {hotel_booked}".format(
                        user_name=u.profile.name or u.username,
                        hotel_booked=info[1].get('hotel')
                    )
                    hotel_reservation.append(hotel_info)
            self.send_group_email(request, users, action="ilt_session_canceled",
                                  hotel_reservation=hotel_reservation,
                                  session_info=session_info)
            self.ilt_enrolled_users.pop(sess_key, {})
            logger.info("Deleted a session, ilt_module: {usage_key}, session_nb: #{sess_key}, User: {user_id}".format(
                usage_key=unicode(self.location),
                sess_key=sess_key,
                user_id=self.runtime.user_id
            ))
        return self.get_student_data()

    @staticmethod
    def session_to_str(sess_key, session):
        default_format = "{start_at} - {end_at} | {timezone} | location: {location}"
        custom_format = configuration_helper.get_value("ILT_DROPDOWN_LIST_FORMAT", "")
        if not custom_format:
            custom_format = default_format

        date_format = configuration_helper.get_value("ILT_DATE_FORMAT", "")
        if date_format:
            start_at = convert_datetime(session['start_at'], date_format)
            end_at = convert_datetime(session['end_at'], date_format)
        else:
            start_at = session['start_at'].replace("T", " ")
            end_at = session['end_at'].replace("T", " ")

        session_data = {
            "start_at": start_at,
            "end_at": end_at,
            "duration": session.get("duration", ""),
            "instructor": session.get("instructor", ""),
            "area_region": session.get("area_region", ""),
            "address": session.get("address", ""),
            "zip_code": session.get("zip_code", ""),
            "city": session.get("city", ""),
            "location_id": session.get("location_id", ""),
            "location": session.get("location", ""),
            "timezone": session.get("timezone", ""),
            "nb": sess_key
        }
        return custom_format.format(**session_data)

    def get_dropdown_list(self, sessions):
        sessions = sorted_sessions(sessions)
        default_format = "{start_at} - {end_at} | {timezone} | location: {location} | #{nb}"
        custom_format = configuration_helper.get_value("ILT_DROPDOWN_LIST_FORMAT", "")
        if not custom_format:
            custom_format = default_format

        date_format = configuration_helper.get_value("ILT_DATE_FORMAT", "")
        if date_format:
            date_format = date_format.replace("YYYY", "%Y").replace("DD", "%d").replace(
                "MM", "%m"
            ).replace("HH", "%H").replace("mm", "%M")

        dropdown_list = []

        if self.deadline is None:
            deadline = 0
        else:
            deadline = self.deadline
        for k, session in sessions:
            class_list = []
            if datetime.now() - decode_datetime(session['end_at']) > timedelta(days=1):
                class_list.append('expire-for-student')
            if datetime.now() - decode_datetime(session['end_at']) > timedelta(days=180):
                class_list.append('expire-for-admin')
            if decode_datetime(session['start_at']) - datetime.now() < timedelta(days=deadline):
                class_list.append('within-deadline')

            extra_class = " ".join(class_list)
            if date_format:
                start_at = decode_datetime(session['start_at']).strftime(date_format)
                end_at = decode_datetime(session['end_at']).strftime(date_format)
            else:
                start_at = session['start_at'].replace("T", " ")
                end_at = session['end_at'].replace("T", " ")
            session_data = {
                "start_at": start_at,
                "end_at": end_at,
                "duration": session.get("duration", ""),
                "instructor": session.get("instructor", ""),
                "area_region": session.get("area_region", ""),
                "address": session.get("address", ""),
                "zip_code": session.get("zip_code", ""),
                "city": session.get("city", ""),
                "location_id": session.get("location_id", ""),
                "location": session.get("location", ""),
                "timezone": session.get("timezone", ""),
                "nb": k
            }
            dropdown_list.append([custom_format.format(**session_data), extra_class, k])
        return dropdown_list

    def sess_with_available_seats(self, sess_key, sess):
        enrolled = self.enrolled_users.get(sess_key, {})
        enrolled_number = len(enrolled)
        expired = datetime.now() > decode_datetime(sess['end_at'])

        for k, v in enrolled.items():
            if v['status'] == 'pending' and expired:
                v['status'] = 'refused'
            if v['status'] == 'refused':
                enrolled_number -= 1
        sess['available_seats'] = int(sess['total_seats']) - enrolled_number
        return sess

    def get_available_seats(self, sess_key):
        """
        get number of available seats, refused users are excluded
        """
        enrolled = self.enrolled_users.get(sess_key, {})
        enrolled_number = len(enrolled)
        for k, v in enrolled.items():
            if v['status'] == 'refused':
                enrolled_number -= 1
        result = int(self.ilt_sessions[sess_key]['total_seats']) - enrolled_number
        return result

    def timezone_offset(self, sess):
        try:
            offset = get_timezone_offset(sess['timezone'])
        except UnknownTimeZoneError:
            offset = 0
        sess['timezone_offset'] = offset
        return sess

    @staticmethod
    def generate_view_id():
        return "".join([random.choice(string.ascii_lowercase) for i in range(20)])

    def student_view(self, context=None):
        """
        The primary view of the ILTXBlock, shown to students
        when viewing courses.
        """
        data = self.get_fields_data()
        html = get_html('static/html/ilt.html', data)
        frag = Fragment(html)
        frag.add_javascript(resource_string("static/js/src/ilt.js"))
        frag.add_javascript_url(self.runtime.local_resource_url(self, "public/js/ics.deps.min.js"))
        frag.add_javascript_url(self.runtime.local_resource_url(self, "public/js/papaparse.min.js"))
        frag.initialize_js('ILTXBlock', {"view_id": data['view_id']})
        return frag

    @json_handler(False, 'GET')
    def student_handler(self, request, data, suffix=''):
        data = self.get_student_data()
        data.update({'domain': request.referer})
        return data

    def get_enrollment(self, user_id, session=None):
        user_id = str(user_id)
        for k, v in self.ilt_enrolled_users.items():
            if not session:
                if user_id in v:
                    return [k, v[user_id]]
            else:
                if user_id in v and session == k:
                    return [k, v[user_id]]

        return [None,
                {
                    "status": None,
                    "accommodation": None,
                    "comment": "",
                    "number_of_one_way": 1,
                    "number_of_return": 1
                }]

    @json_handler(True, 'GET')
    def get_enrolled_users(self, request, data, suffix=''):
        result = []
        session = request.GET.get('session')
        if not session:
            return result
        _ = self.ugettext
        for sess, stds, in self.enrolled_users.iteritems():
            if sess != session:
                continue
            users = User.objects.filter(id__in=stds).prefetch_related('profile')
            for u in users:
                if stds[str(u.id)]['status'] == "accepted" or stds[str(u.id)]['status'] == "confirmed":
                    result.append({'username': u.username, 'session': self.session_to_str(sess, self.sessions[sess]),
                                   'country': unicode(u.profile.country.name),
                                   'full_name': u.profile.name, 'attendance': ''})
        return result

    @json_handler(True, 'POST')
    def grade_users(self, request, data, suffix=''):
        all_users = []
        for i in self.enrolled_users.values():
            all_users = all_users + i.keys()
        eval_users = data.keys()
        users = User.objects.filter(username__in=list(eval_users))
        grade_info = [{
                    'value': self.max_score(),
                    'max_value': self.max_score(),
                    'user_id': user.id,
                } for user in users if str(user.id) in all_users]
        self.runtime.publish(self, 'ilt_grade', grade_info)
        return {}

    @json_handler(True, 'POST')
    def batch_enroll(self, request, data, suffix=''):
        _ = self.ugettext
        nb_learners_to_enroll = len(_split_input_list(data.get('identifiers')))
        if configuration_helper.get_value("ILT_BYPASS_VALIDATION_WORKFLOW", "mandatory") == "mandatory":
            bypass_validation = True
        elif configuration_helper.get_value("ILT_BYPASS_VALIDATION_WORKFLOW", "mandatory") == "hidden":
            bypass_validation = False
        else:
            bypass_validation = data.get('bypass_validation')
        sess_key = data.get('session')
        sess = self.ilt_sessions[sess_key]
        available_seats = self.sess_with_available_seats(sess_key, sess).pop('available_seats')
        if nb_learners_to_enroll > available_seats:
            result = _("There are not enough seats available!")
            message = {"result": result, "data": self.get_student_data()}
            return message

        def compare_session(enrolled_session, session, user, status=None, notify_by_email=True):
            if enrolled_session and status != 'refused':
                return _('user already enrolled in session')
            else:
                info = {
                    "status": "pending",
                    "accommodation": "no",
                    "comment": "",
                    "number_of_one_way": 1,
                    "number_of_return": 1,
                    "hotel": ""
                }
                self._enroll(session, info, user, request,
                             bypass_validation=bypass_validation, notify_by_email=notify_by_email)
                return _('enroll success')

        return self._batch_toggle_enrollment(data, compare_session, request)

    @json_handler(False, 'POST')
    def batch_unenroll(self, request, data, suffix=''):
        _ = self.ugettext

        def compare_session(enrolled_session, session, user, status=None, notify_by_email=True):
            if enrolled_session and session == enrolled_session:
                self._unenroll(enrolled_session, user, request, action='ilt_unenrolled')
                return _('unenroll success')
            else:
                return _('user has not been enrolled into this session')
        return self._batch_toggle_enrollment(data, compare_session, request, action="ilt_batch_unenroll")

    def _batch_toggle_enrollment(self, data, func, request, action="batch_enroll"):
        _ = self.ugettext
        identifiers = _split_input_list(data.get('identifiers'))
        session = data['session']
        result = {}
        message = {}
        learners = []
        hotel_reservation = []
        session_info = self.ilt_sessions.get(session)
        for identifier in identifiers:
            try:
                user = get_student_from_identifier(identifier)
                learners.append(user)
                CourseEnrollment.objects.get(user=user, course_id=self.runtime.course_id)
            except User.DoesNotExist:
                result[identifier] = _("user does not exist")
                continue
            except MultipleObjectsReturned:
                result[identifier] = _("multiple users found, please input a unique username")
            except CourseEnrollment.DoesNotExist:
                result[identifier] = _("user has not been enrolled into this course")
                continue

            info = self.get_enrollment(
                user.id,
                session if '_enroll' not in action else None    # Only specify session_id for unenrollment
            )
            if info[1].get('hotel', '') != '':
                hotel_info = "Name: {user_name}, Hotel Booked: {hotel_booked}".format(
                    user_name=user.profile.name or user.username,
                    hotel_booked=info[1].get('hotel')
                )
                hotel_reservation.append(hotel_info)
            enrolled_session = info[0]

            try:
                result[identifier] = func(
                    enrolled_session, session, user, status=info[1].get('status'),
                    notify_by_email=data.get('notify_by_email', True))
            except JsonHandlerError as e:
                return e.get_response()
        message['result'] = result
        message['data'] = self.get_student_data()

        if learners and action == 'ilt_batch_unenroll':
            self.send_group_email(request, learners, action,
                                  hotel_reservation=hotel_reservation,
                                  session_info=session_info)
        logger.info("Batch enrollment, action: {action}, user: {user_id}, ilt_module: {usage_key}, "
                    "session_nb: #{sess_key}, identifiers: {identifiers}, result: {result}".format(
                        action=action,
                        user_id=self.runtime.user_id,
                        usage_key=unicode(self.location),
                        sess_key=session,
                        identifiers=identifiers,
                        result=result
                    ))
        return message

    def _enroll(self, session, info, user, request, bypass_validation=True, notify_by_email=True):
        if self.get_available_seats(session) <= 0:
            raise JsonHandlerError(400, "No available seats")

        number_of_one_way = info['number_of_one_way']
        number_of_return = info['number_of_return']
        try:
            info['number_of_one_way'] = int(number_of_one_way)
        except Exception as e:
            info['number_of_one_way'] = 0
        try:
            info['number_of_return'] = int(number_of_return)
        except Exception as e:
            info['number_of_return'] = 0

        enrollment = self.get_enrollment(user.id)

        # in case previous request is refused and learner can re-enroll again
        if enrollment[0] and enrollment[1]['status'] == 'refused':
            # remove the previous request
            self.ilt_enrolled_users[enrollment[0]].pop(str(user.id), {})

        if session not in self.ilt_enrolled_users:
            self.ilt_enrolled_users[session] = {}

        session_info = self.sessions[session]

        accommodation = configuration_helper.get_value("ILT_ACCOMMODATION_ENABLED", False)

        if bypass_validation:
            info['status'] = "confirmed"
            if notify_by_email:
                self.send_email('ilt_confirmed', user, request, session_info=session_info)
        else:
            if user.profile.lt_ilt_supervisor:
                info['status'] = "pending"
                if not configuration_helper.get_value('ILT_FOLLOW_UP_ENABLED', False):
                    self.send_email('ilt_validate', user, request, session_info=session_info)
            else:
                if accommodation and info['accommodation'] == 'yes':
                    info['status'] = "accepted"
                else:
                    info['status'] = "confirmed"
                    if notify_by_email:
                        self.send_email('ilt_confirmed', user, request, session_info=session_info)
        self.ilt_enrolled_users[session][str(user.id)] = info

    def _unenroll(self, session, user, request, action="ilt_self_unenroll"):
        info = self.ilt_enrolled_users[session].pop(str(user.id), {})
        hotel_info = ''
        session_info = self.sessions[session]
        if info['accommodation'] == 'yes' and info.get('hotel', '') != '':
            hotel_info = "Name: {user_name}, Hotel Booked: {hotel_booked}".format(
                user_name=user.profile.name or user.username,
                hotel_booked=info.get('hotel')
            )
        if settings.LEARNER_NO_EMAIL and user.email.endswith(settings.LEARNER_NO_EMAIL) and action == "ilt_unenrolled":
            pass
        else:
            self.send_email(action, user, request, hotel_info=hotel_info, session_info=session_info)

    @json_handler(False, 'POST')
    def toggle_enrollment(self, request, data, suffix=''):
        session = data['session']
        request_info = data['request_info']
        if not session:
            return {}

        user = self.get_current_user()
        enrolled_session = self.get_enrollment(user.id)
        if enrolled_session[0] and enrolled_session[1]['status'] != 'refused':  # already enrolled
            self._unenroll(enrolled_session[0], user, request)
            logger.info("Self unenroll, learner: {user_id}, ilt_module: {usage_key}, session_nb: #{sess_key}".format(
                user_id=self.runtime.user_id,
                usage_key=unicode(self.location),
                sess_key=session
            ))
        else:  # not enrolled
            try:
                self._enroll(session, request_info, user, request)
                logger.info("self enroll, learner: {user_id}, ilt_module: {usage_key}, "
                            "session_nb: #{sess_key}, request_info: {info}".format(
                                user_id=self.runtime.user_id,
                                sess_key=session,
                                usage_key=unicode(self.location),
                                info=request_info
                            ))
            except JsonHandlerError as e:
                return e.get_response()
        return self.get_student_data()

    @json_handler(False, 'POST')
    def batch_update_accepted_requests(self, request, data, suffix=''):
        """
        when course admin edits accepted/confirmed request from Enrollment Management tab,
        in this case, the session number is still the same, an ilt_request_updated email is sent
        to learner. If the previous "accommodation" value was yes and "hotel" was filled with
        hotel information, and then "accommodation" is changed to "no", then an ilt_hotel_cancel
        email is sent to course admin.
        """
        session = data['session']
        learner_requests = data['learner_requests']
        enrolled_users = self.ilt_enrolled_users[session]
        hotel_reservation = []
        for user_id, rqst in learner_requests.items():
            old_request = enrolled_users[user_id]
            user = User.objects.get(id=user_id)
            updated = False
            confirmed = False
            if old_request['status'] != 'pending':
                for k, v in old_request.items():
                    if k in ['status', 'hotel']:
                        continue
                    if v != rqst[k]:
                        updated = True
                        if k == 'accommodation' and v == 'yes':
                            if old_request.get('hotel'):
                                hotel_info = "Name: {user_name}, Hotel Booked: {hotel_booked}".format(
                                    user_name=user.profile.name,
                                    hotel_booked=old_request.get('hotel')
                                )
                                hotel_reservation.append(hotel_info)
                                old_request['hotel'] = ''
                            else:
                                old_request['status'] = 'confirmed'
                                confirmed = True
                        if k == 'accommodation' and v == 'no':
                            old_request['status'] = 'accepted'
                        if k in ['number_of_one_way', 'number_of_return']:
                            try:
                                old_request[k] = int(rqst[k])
                            except Exception as e:
                                old_request[k] = 0
                        else:
                            old_request[k] = rqst[k]
            else:
                updated_pending = False
                for k, v in old_request.items():
                    if k in ['status', 'hotel']:
                        continue
                    if v != rqst[k]:
                        if k in ['number_of_one_way', 'number_of_return']:
                            try:
                                old_request[k] = int(rqst[k])
                            except Exception as e:
                                old_request[k] = 0
                        else:
                            old_request[k] = rqst[k]
                        updated_pending = True
                if updated_pending:
                    session_info = self.ilt_sessions[session]
                    if old_request['accommodation'] == 'yes':
                        old_request['status'] = 'accepted'
                        self.send_email('ilt_request_updated', user, request, session_info=session_info,
                                        request_info=old_request)
                    else:
                        old_request['status'] = 'confirmed'
                        self.send_email('ilt_confirmed', user, request, session_info=session_info,
                                        request_info=old_request)
            if updated:
                session_info = self.ilt_sessions[session]
                if confirmed:
                    self.send_email('ilt_confirmed', user, request, session_info=session_info,
                                        request_info=old_request)
                else:
                    self.send_email('ilt_request_updated', user, request, session_info=session_info,
                                request_info=old_request)
        if hotel_reservation:
            course_admins = CourseInstructorRole(self.course_id).users_with_role()
            course = modulestore().get_course(self.course_id)
            params = {
                'name': '',
                'ilt_link': request.referer,
                'ilt_name': self.display_name,
                'site_name': None,
                'hotel_info': hotel_reservation,
                'message': 'ilt_hotel_cancel',
                'action': 'ilt_hotel_cancel',
                'course_name': course.display_name,
                'session_info': session_info
            }
            for u in course_admins:
                params['name'] = u.profile.name or u.username
                send_mail_to_student(u.email, params, language=get_user_email_language(u))
        return self.get_student_data()

    @json_handler(False, 'POST')
    def batch_switch_session(self, request, data, suffix=''):
        """
        when course admin change learner's selected session to another, in this case, the request
        information remains the same, an ilt_session_changed email should be sent to learner.
        """
        # TODO: in the future when ILT supports multi-session enrollment, we should check if learner
        # TODO: is already enrolled in the new session
        old_session = data['old_session']
        new_session = data['new_session']
        old_session_enrolled = self.ilt_enrolled_users[old_session]
        if new_session not in self.ilt_enrolled_users:
            self.ilt_enrolled_users[new_session] = {}
        new_session_enrolled = self.ilt_enrolled_users[new_session]
        learners = data['learners']
        session_info = self.ilt_sessions[new_session]
        for user_id in learners:
            new_session_enrolled[user_id] = old_session_enrolled.pop(user_id)
            user = User.objects.get(id=user_id)
            new_request = new_session_enrolled[user_id]
            if new_request['status'] == 'pending':
                if new_request['accommodation'] == 'yes':
                    new_request['status'] = 'accepted'
                    self.send_email('ilt_session_changed', user, request, session_info=session_info)
                else:
                    new_request['status'] = 'confirmed'
                    self.send_email('ilt_confirmed', user, request, session_info=session_info,
                                    request_info=new_request)
            else:
                self.send_email('ilt_session_changed', user, request, session_info=session_info)
        return self.get_student_data()

    @json_handler(False, 'POST')
    def batch_accept_requests(self, request, data, suffix=''):
        """
        1. request pending + accommodation accepted by course admin (--> accepted) => no email
        2. request pending + NO accommodation accepted by course admin (--> confirmed)
            => ilt_confirmed_email sent to learner
        """
        session = data['session']
        learner_requests = data['learner_requests']
        enrolled_users = self.ilt_enrolled_users[session]
        for user_id, rqst in learner_requests.items():
            old_request = enrolled_users[user_id]
            user = User.objects.get(id=user_id)
            if old_request['status'] == 'pending':
                if old_request['accommodation'] == 'yes':
                    old_request['status'] = 'accepted'
                else:
                    old_request['status'] = 'confirmed'
                    session_info = self.ilt_sessions[session]
                    self.send_email('ilt_confirmed', user, request, session_info=session_info,
                                    request_info=old_request)
        return self.get_student_data()

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("ILTXBlock",
             """<ilt/>
             """),
            ("Multiple ILTXBlock",
             """<vertical_demo>
                <ilt/>
                <ilt/>
                <ilt/>
                </vertical_demo>
             """),
        ]

    def get_all_list(self):
        """
        return two dicts, one is for all requests
        the other is for all requests with accommodation
        """
        all_list = {}
        validation_list_with_accommodation = {}
        for k, v in self.enrolled_users.items():
            sublist = []
            accommodation_sublist = []
            for u, i in v.items():
                if i['status'] != 'refused':
                    try:
                        user = User.objects.get(id=u)
                        last_name = user.last_name
                        name = user.profile.name
                        store_id = user.profile.lt_address_2
                        user_name = user.username
                        info = {
                            "user_id": u,
                            "name": name,
                            "employee_id": user_name,
                            "last_name": last_name,
                            "checked": False,
                            "store_id": store_id
                        }
                        info.update(i)
                        sublist.append(info)
                    except User.DoesNotExist:
                        logger.exception("Ignore user id with %s, doesn't exist anymore" % u)
                        v.pop(u)

                    if i['accommodation'] == 'yes' and i['status'] != 'pending':
                        accommodation_sublist.append(info)
            sublist.sort(key=lambda x: (x['status'], x['last_name']))
            all_list[k] = sublist
            validation_list_with_accommodation[k] = accommodation_sublist
        return all_list, validation_list_with_accommodation

    @json_handler(True, 'POST')
    def accommodation_validate(self, request, data, suffix=""):
        info = data['validation']
        session = data['session']
        enrolled = self.enrolled_users[session]
        session_info = self.sessions[session]
        for i in info:
            user = User.objects.get(id=i['user_id'])
            # hotel info update, status is already confirmed
            if enrolled[i["user_id"]]["status"] == "confirmed":
                if i["hotel"] != enrolled[i["user_id"]].get("hotel", ""):
                    enrolled[i["user_id"]]["hotel"] = i["hotel"]
                    self.send_email('ilt_hotel_updated', user, request, session_info=session_info)

            else:
                if i.get("hotel", "") != "":
                    enrolled[i["user_id"]]["status"] = "confirmed"
                    enrolled[i["user_id"]]["hotel"] = i["hotel"]
                    self.send_email('ilt_confirmed', user, request, session_info=session_info)
        return self.get_student_data()
