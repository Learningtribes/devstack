# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from copy import deepcopy
import io
import os
import pkg_resources
import uuid
import logging
import re
from collections import namedtuple

from lxml import etree
import six
from six.moves.urllib.parse import unquote, urlparse
import user_agents
import boto3
import traceback

from crum import get_current_request
from django.template import Context, Template
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.conf import settings
from django.contrib.auth.models import User
from xblock.core import XBlock
from xblock.exceptions import XBlockSaveError, JsonHandlerError
from xblock.scorable import Score
from xblock.fields import String, Scope, Dict, Boolean, Float, List
from xblock.reference.plugins import Filesystem

from web_fragments.fragment import Fragment
from webob.response import Response
from fs.copy import copy_dir
from fs.zipfs import ZipFS
from zipfile import BadZipFile, ZipFile
from io import BytesIO
from .studio_editable import StudioEditableXBlockMixin
from .fields import File


try:
    from contentstore.views.assets import update_course_run_asset
    from xmodule.progress import Progress
    from xmodule.contentstore.content import StaticContent
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    pass
from .scorm_default import *
from .fields import DateTime
from .mixins import ScorableXBlockMixin

from .config import SupportedScormResources, SUPPORTED_SCORM_RESOURCES
from fs.osfs import OSFS

from student.roles import get_platform_role, DEVELOPER_LEVEL, PLATFORM_SUPER_ADMIN_LEVEL

logging.getLogger('botocore').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
# Make '_' a no-op so we can scrape strings
_ = lambda text: text


def dt2str(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%f%z')


def str2dt(dtstr):
    return parse_datetime(dtstr)


SCORM_STATUS = namedtuple('ScormStatus', [
    'SUCCEED', 'FAILED', 'IN_PROGRESS', 'UNATTENDED'])(
    'SUCCEED', 'FAILED', 'IN PROGRESS', 'UNATTENDED')

SCORM_VERSION = namedtuple('ScormVersion', ['V12', 'V2004'])('SCORM12', 'SCORM2004')


@XBlock.needs('request', 'fs', 'i18n', 'user')
class ScormXBlock(StudioEditableXBlockMixin, ScorableXBlockMixin, XBlock):
    """
    all fields private to `scorm` are prefix with `scorm`, in case any conflict
    with internal fields.
    """
    display_name = String(
        default="SCORM",
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Display Name"),
        help=_("Display name for this module"),
    )

    due = DateTime(
        default="2000-01-01T00:00:00.00+0000",
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Due Date"),
        help=_("Due Date"),
    )

    has_score = Boolean(
        default=False,
        scope=Scope.settings,
        enforce_type=True,
        display_name=_('Score'),
        help=_("Does this SCORM need to be scored?")
    )

    icon_class = String(
        default='problem',
        scope=Scope.settings,
        values=("problem", "video", "other"),
        enforce_type=True,
        display_name=_("Icon"),
        help=_("Icon used in course page")
    )

    weight = Float(
        default=1.0,
        scope=Scope.settings,
        values={"min": 0, "step": 0.1},
        enforce_type=True,
        display_name=_('Weight'),
        help=_("Relative weight in this course section")
    )

    ratio = String(
        default="16:9",
        scope=Scope.settings,
        values=("16:9", "4:3", "1:1"),
        enforce_type=True,
        display_name=_('Ratio'),
        help=_("Aspect ratio of this module")
    )

    open_new_tab = Boolean(
        default=True,
        scope=Scope.settings,
        enforce_type=True,
        display_name=_('Full screen'),
        help=_("Allow the module to open in full screen")
    )

    fs = Filesystem(scope=Scope.settings)

    scorm_pkg = File(
        accept="application/zip",
        default="",
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("SCORM module"),
        help=_("SCORM module in .zip format") + '; ' + _("Size limit: ") + '300MB',
        extra_description=_("Required (Size limit: 300MB)")
    )

    scorm_pkg_filename = String(
        display_name=_("SCORM filename"),
        scope=Scope.settings,
        default="",
        resettable_editor=False,
        readonly=True
    )

    scorm_file = String(
        display_name=_("compatible with old version scorm file"),
        scope=Scope.settings,
        default="old"
    )

    scorm_pkg_version = String(
        default=SCORM_VERSION.V12,
        scope=Scope.settings,
        values=SCORM_VERSION,
        enforce_type=True,
        display_name=_("Version"),
        help=_("Version of scorm, 1.2 or 2004")
    )

    scorm_pkg_modified = DateTime(
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Upload time"),
        help=_("SCORM package upload time utc")
    )

    _scorm_runtime_data = Dict(
        default={},
        scope=Scope.user_state,
        enforce_type=True
    )

    scorm_runtime_modified = DateTime(
        scope=Scope.user_state,
        enforce_type=True,
        display_name=_("Runtime Modified Time"),
        help=_("SCORM runtime modified time utc")
    )

    scorm_status = String(
        default=SCORM_STATUS.UNATTENDED,
        scope=Scope.user_state,
        values=SCORM_STATUS,
        enforce_type=True
    )

    success_status = String(
        scope=Scope.user_state,
        default='unknown'
    )

    scorm_score = Float(
        default=0,
        scope=Scope.user_state,
        enforce_type=True
    )

    lesson_score = Float(
        scope=Scope.user_state,
        default=0
    )

    scorm_allow_rescore = Boolean(
        default=True,
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Rescore"),
        help=_("Does this SCORM allow users to submit answer multiple times?")
    )

    version_scorm = String(
        default="SCORM_12",
        scope=Scope.settings,
    )

    scorm_modified = DateTime(
        scope=Scope.settings,
    )

    scorm_launch_data = String(
        default="",
        scope=Scope.settings
    )

    instruction = String(
        default="",
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Instruction")
    )

    cover_image = File(
        accept="image/*",
        default="/static/xblock/scormxblock/scorm-cover-0.jpg",
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Cover Image"),
        help=_("Size recommandation : 965x270px"),
        extra_description=_("Size recommandation : 965x270px"),
    )

    cover_images = List(
        scope=Scope.settings,
    )

    editable_fields = (
        'scorm_pkg', 'scorm_pkg_filename', 'display_name',
        'has_score', 'weight',
        'instruction', 'cover_image'
    )
    has_author_view = True

    def get_s3_client(self):
        """
        Get S3 client with credentials from settings
        Returns:
            boto3.client: Configured S3 client
        """
        aws_access_key_id = settings.DJFS.get('aws_access_key_id')
        aws_secret_access_key = settings.DJFS.get('aws_secret_access_key')
        return boto3.client('s3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key)

    # region Studio handler
    @XBlock.handler
    def studio_upload_files(self, request, suffix=''):
        from django.utils.translation import gettext as _

        try:
            pkg = request.POST.get('scorm_pkg', None)
            cover_image = request.POST.get('cover_image', None)
            cover_images = request._request.FILES.getlist('cover_images[]')
            limited_file_size = 300 * 1024 * 1024  # 300 MB

            user = request._request.user

            def check_file_size(file):
                return limited_file_size < file.size

            def has_permission(user):
                requestor_access_level = get_platform_role(user)
                return requestor_access_level in (DEVELOPER_LEVEL, PLATFORM_SUPER_ADMIN_LEVEL)

            if pkg and check_file_size(pkg.file) and not has_permission(user):
                return Response(
                    status=403,
                    json_body={'error': _('Your file is too large.')},
                    content_type='application/json'
                )

            if pkg:
                try:
                    with ZipFile(pkg.file, 'r') as zip_fs:
                        for member in zip_fs.namelist():
                            normalized = member.replace('\\', '/')
                            parts = normalized.split('/')
                            if (normalized.startswith('/') or '\x00' in member or
                                    any(part == '..' for part in parts) or
                                    re.match(r'^[A-Za-z]:', normalized)):
                                return Response(
                                    status=400,
                                    json_body={'error': _('The SCORM package contains an invalid path.')},
                                    content_type='application/json'
                                )
                        mf = zip_fs.read('imsmanifest.xml')
                        self.scorm_pkg_version, scorm_index, scorm_launch = self._get_scorm_info(mf)
                except (BadZipFile, KeyError, etree.XMLSyntaxError):
                    return Response(
                        status=400,
                        json_body={'error': _('The SCORM package is invalid.')},
                        content_type='application/json'
                    )

                pkg_id = uuid.uuid4().hex
                pkg_id = self._upload_scorm_pkg(pkg, pkg_id)
                self.scorm_pkg = os.path.join(pkg_id, scorm_index)
                self.scorm_pkg_modified = timezone.now()
                if scorm_launch is not None:
                    self.scorm_launch_data = str(scorm_launch)

                # store SCORM zip file
                self._upload_scorm_zip(pkg.file, pkg_id)
                self.scorm_pkg_filename = pkg.filename

            if cover_images:
                self.cover_images = [
                    self._upload_cover_image(c) for c in cover_images
                ]

            if cover_image:
                cover_image_hash = cover_image.split('-')[-1]
                for optional_cover_image in self.cover_images:
                    if cover_image_hash in optional_cover_image:
                        self.cover_image = optional_cover_image
                        break
                else:
                    self.cover_image = cover_image

            return Response(
                status=200,
                json_body={'status': 'success'},
                content_type='application/json'
            )

        except Exception as e:
            logging.error(
                u"Error in studio_upload_files: {0}\n{1}".format(str(e), traceback.format_exc())
            )
            return Response(
                status=500,
                json_body={'error': _('An error occurred while uploading files.')},
                content_type='application/json'
            )

    def _read_zip(self, pkg):
        input_zip = ZipFile(pkg.file)
        zip_contents = {}

        for filename in input_zip.namelist():
            if six.PY2 and isinstance(filename, six.text_type):
                newname = filename.encode('utf-8')
            elif six.PY2 and isinstance(filename, six.binary_type):
                try:
                    filename.decode('utf-8')
                    newname = filename
                except UnicodeDecodeError:
                    uname = filename.decode('latin-1')
                    newname = uname.encode('utf-8')
            else:
                newname = filename
            zip_contents[newname] = input_zip.read(filename)

        in_memory = BytesIO()
        zf = ZipFile(in_memory, mode="w")
        for x, y in zip_contents.items():
            zf.writestr(x, y)
        zf.close()
        in_memory.seek(0)

        return ZipFS(in_memory), zip_contents

    def _upload_scorm_zip(self, zip_file, pkg_id):
        """
        Upload SCORM zip to s3 storage
        :param zip_file:
        :param pkg_id:
        :return:
        """
        try:
            zip_file.seek(0)
            # Copy bytes from any file-like object instead of relying on a specific wrapper type.
            if hasattr(zip_file, 'chunks'):
                bytes_io = BytesIO(b''.join(zip_file.chunks()))
            else:
                bytes_io = BytesIO(zip_file.read())

            bytes_io.seek(0)
            # uuid.hex is text on Py3 and bytes-like str on Py2; never call .decode on text.
            file_path = six.ensure_text(pkg_id) + u'.zip'
            if isinstance(self.fs, OSFS):
                with self.fs.open(file_path, 'wb') as os_file:
                    os_file.write(bytes_io.getvalue())
            else:
                with self.fs.open(file_path, 'wb', acl='public-read') as s3_file:
                    s3_file.write(bytes_io.getvalue())
        except IOError:
            raise XBlockSaveError([], ['scorm_pkg'], _('Error in uploading scorm package'))

    def _upload_scorm_pkg(self, pkg, pkg_id):
        fs, zip_contents = self._read_zip(pkg)
        _ = self.runtime.service(self, 'i18n').ugettext
        pkg_id_text = six.ensure_text(pkg_id)

        try:
            if isinstance(self.fs, OSFS):
                copy_dir(fs, u'/', self.fs, pkg_id_text)
            else:
                s3_client = self.get_s3_client()
                # Get S3 target prefix from XBlock filesystem
                target_prefix = None
                if hasattr(self.fs, 'dir_path'):
                    target_prefix = self.fs.dir_path.lstrip('/')

                if target_prefix:
                    s3_base_path = os.path.join(target_prefix, pkg_id_text)
                else:
                    s3_base_path = pkg_id_text

                file_count = len(zip_contents)
                logging.info("Uploading {0} files from SCORM package to S3...".format(file_count))

                from concurrent.futures import ThreadPoolExecutor, as_completed
                from functools import partial

                def upload_file_to_s3(file_path, file_content):
                    """Upload a single file to S3"""
                    try:
                        if isinstance(file_path, six.binary_type):
                            file_path = file_path.decode('utf-8')
                        s3_key = os.path.join(s3_base_path, file_path)

                        # Determine content type based on file extension
                        content_type = 'application/octet-stream'
                        if file_path.endswith('.html') or file_path.endswith('.htm'):
                            content_type = 'text/html'
                        elif file_path.endswith('.css'):
                            content_type = 'text/css'
                        elif file_path.endswith('.js'):
                            content_type = 'application/javascript'
                        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                            content_type = 'image/jpeg'
                        elif file_path.endswith('.png'):
                            content_type = 'image/png'
                        elif file_path.endswith('.gif'):
                            content_type = 'image/gif'
                        elif file_path.endswith('.svg'):
                            content_type = 'image/svg+xml'
                        elif file_path.endswith('.xml'):
                            content_type = 'application/xml'

                        # Upload file to S3 with public read access
                        s3_client.put_object(
                            Bucket=settings.DJFS.get('bucket'),
                            Key=s3_key,
                            Body=file_content,
                            ContentType=content_type,
                            ACL='public-read'
                        )
                        return True, file_path
                    except Exception as e:
                        logging.error(
                            u"Error uploading {0}: {1}\n{2}".format(file_path, str(e), traceback.format_exc())
                        )
                        return False, file_path

                # Create thread pool with max 10 workers for parallel upload
                with ThreadPoolExecutor(max_workers=10) as executor:
                    # Submit all upload tasks to thread pool
                    future_to_file = {
                        executor.submit(upload_file_to_s3, file_path, file_content): file_path
                        for file_path, file_content in zip_contents.items()
                    }

                    # Track upload progress
                    completed = 0
                    failed_files = []

                    # Process completed tasks
                    for future in as_completed(future_to_file):
                        completed += 1
                        success, file_path = future.result()

                        if not success:
                            failed_files.append(file_path)

                        logging.info(u"Upload progress: {0}/{1} - {2}".format(completed, file_count, file_path))

                # Check if any files failed to upload
                if failed_files:
                    logging.error(u"Failed to upload {0} files: {1}".format(len(failed_files), failed_files))
                    raise XBlockSaveError([], ['scorm_pkg'], _('Error in uploading some files to S3'))

        except IOError:
            raise XBlockSaveError([], ['scorm_pkg'], _('Error in uploading scorm package'))
        return pkg_id

    def _upload_cover_image(self, cover_image):
        if type(cover_image) is str:
            return cover_image

        content = update_course_run_asset(self.course_id, cover_image)

        return StaticContent.serialize_asset_key_with_slash(content.location)

    @staticmethod
    def _get_scorm_info(manifest):
        index_page = 'index.html'
        launch_data = None
        datafromlms = 'organizations/organization/item/adlcp:datafromlms'
        root = etree.fromstring(manifest)
        id_ref = root.find('organizations/organization/item', root.nsmap).get('identifierref')
        resources = root.find('resources', root.nsmap)
        resource = resources.findall('resource', root.nsmap)
        schemaversion = root.find('metadata/schemaversion', root.nsmap)
        scorm_version = SCORM_VERSION.V12
        if resource:
            if len(resource) > 1:
                for i in resource:
                    if i.get('identifier') == id_ref:
                        index_page = i.get('href')
            else:
                index_page = resource[0].get('href')

        if (schemaversion is not None) and (re.match('^1.2$', schemaversion.text) is None):
            scorm_version = SCORM_VERSION.V2004
            datafromlms = 'organizations/organization/item/adlcp:dataFromLMS'
        launch_data = root.find(datafromlms, root.nsmap)
        if launch_data is not None:
            launch_data = launch_data.text
        return scorm_version, index_page, launch_data

    # endregion

    # region Runtime functions
    def max_score(self):
        return 1.0

    def allows_rescore(self):
        return self.scorm_allow_rescore

    def set_score(self, score):
        self.scorm_score = self.max_score() * score.raw_earned / score.raw_possible

    def get_score(self):
        return Score(raw_possible=self.max_score(), raw_earned=self.scorm_score)

    def calculate_score(self):
        return self.get_score()

    def publish_grade(self, score=None, only_if_higher=None):
        """Publishes the student's current grade to the system as an event

            Used by method `def override_score_module_state()` : ( https://github.com/Learningtribes/platform/blob/bf7b77550a4ed83fe29f1ac60447f85d327d6e95/lms/djangoapps/instructor_task/tasks_helper/module_state.py#L263 )
            while user clicking on Button "Override Score".

        """
        if not score:
            score = self.calculate_score()

        self._publish_grade(score, only_if_higher)

        return {
            'grade': score.raw_earned,
            'max_grade': score.raw_possible
        }

    def has_submitted_answer(self):
        return self.scorm_status != SCORM_STATUS.UNATTENDED

    def get_progress(self):
        pg = 0
        if self.scorm_pkg_version == SCORM_VERSION.V2004:
            try:
                pg = float(self.scorm_runtime_data.get('cmi.progress_measure', 0))
            except ValueError:
                pg = 0
        return Progress(pg, 1)

    # endregion

    @property
    def scorm_runtime_data(self):
        return self._scorm_runtime_data

    @scorm_runtime_data.setter
    def scorm_runtime_data(self, value):
        # TODO: add validation ss
        self._scorm_runtime_data = value

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)

        # if isinstance(data, unicode):
        # raise ValueError("isinstance")
        return data if isinstance(data, six.text_type) else data.decode("utf8")

    def render_template(self, template_path, context={}):

        """Evaluate a template by resource path, applying the provided context"""
        SupportedScormResources.assign_scorm_handle(self)

        template = Template(self.resource_string(template_path))

        return template.render(Context(context))

    def get_fields_data(self, only_value=False, *fields):

        data = {}
        pkg_url = ''
        for k, v in six.iteritems(self.fields):
            if k in fields:
                if not only_value:
                    data[k] = v
                data["{}_value".format(k)] = getattr(self, k)

        if 'scorm_pkg' in data and self.scorm_pkg:
            pkg_url = self.fs.get_url(self.scorm_pkg)
        if 'scorm_pkg' in data and self.scorm_pkg == '' and self.scorm_file != 'old':
            scorm_file_string = self.scorm_file[:22] + 'scorm/' + self.scorm_file[22:]
            pkg_url = self.fs.get_url(scorm_file_string)
        if pkg_url:
            if settings.DJFS['type'] == 's3fs':
                pkg_url = unquote(urlparse(pkg_url).path)
            data['scorm_pkg_value'] = pkg_url

        if 'cover_image' in data and self.cover_image:
            cover_image_url = self.fs.get_url(self.cover_image)
            if cover_image_url:
                if settings.DJFS['type'] == 's3fs':
                    cover_image_url = unquote(urlparse(cover_image_url).path)
                data['cover_image_value'] = cover_image_url

        if 'scorm_score' in data and self.scorm_score == float(0) and self.lesson_score != float(0):
            data['scorm_score_value'] = self.lesson_score

        if 'scorm_status' in data and self.scorm_status == SCORM_STATUS.UNATTENDED and self.success_status != 'unknown':
            data['scorm_status_value'] = self.success_status

        if 'scorm_pkg_version_value' in data and self.scorm_pkg_version == SCORM_VERSION.V12 and self.version_scorm == 'SCORM_2004':
            data['scorm_pkg_version_value'] = SCORM_VERSION.V2004

        if 'scorm_pkg_modified_value' in data and not self.scorm_pkg_modified and self.scorm_modified:
            data['scorm_pkg_modified_value'] = self.scorm_modified

        for k, v in data.items():
            if isinstance(v, timezone.datetime):
                data[k] = dt2str(v)

        # logger.info("Return: " + str(data))

        return data

    def get_student_data(self):
        fields_data = self.get_fields_data(False, 'scorm_score', 'weight', 'ratio',
                                           'has_score', 'scorm_status', 'scorm_pkg',
                                           'scorm_file', 'lesson_score', 'success_status',
                                           'open_new_tab', 'instruction', 'cover_image')
        fields_data['graded_status'] = 'ungraded'
        if self.graded and fields_data['has_score'] and fields_data['weight'] != 0:
            fields_data['graded_status'] = 'graded'
        fields_data['display_name'] = self.display_name
        return fields_data

    def student_view(self, context=None):
        template = self.render_template('static/html/scormxblock.html', self.get_student_data())
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/scormxblock.js"))
        frag.initialize_js('ScormXBlock',
                           json_args=self.get_fields_data(True, 'scorm_pkg_version', 'scorm_pkg_modified', 'ratio',
                                                          'version_scorm', 'scorm_modified'))
        return frag

    def author_view(self, context):

        """View of Studio Courses page"""
        fields_data = self.get_fields_data(False,
                                           'scorm_pkg',
                                           'open_new_tab', 'instruction', 'cover_image'
                                           )
        scorm_path = fields_data.get('scorm_pkg_value')
        if scorm_path:
            cms_path = scorm_path.replace('/xblock/', '/xblock_resource/')
            fields_data['cms_path'] = cms_path
        frag = Fragment()
        frag.add_content(
            self.render_template('static/html/author_view.html', dict(fields_data,
                                                                      external_resources=SUPPORTED_SCORM_RESOURCES,
                                                                      lms_root_url=configuration_helpers.get_value(
                                                                          'LMS_ROOT_URL', settings.LMS_ROOT_URL),
                                                                      usd_svg=self.resource_string(
                                                                          'static/images/dollar.svg')
                                                                      ))
        )
        frag.add_css(self.resource_string('static/css/scormxblock.css'))
        # Inject js Script to <head> in file: cms/static/js/views/xblock.js#L218
        frag.add_javascript(self.resource_string('static/js/src/scormxblock.js'))
        frag.initialize_js('ScormXBlock',
                           json_args=self.get_fields_data(True, 'scorm_pkg_version', 'scorm_pkg_modified', 'ratio',
                                                          'version_scorm', 'scorm_modified'))

        return frag

    def studio_view(self, context):
        fragment = super(ScormXBlock, self).studio_view(context)
        fragment.add_javascript(self.resource_string('static/js/src/studio.js'))

        return fragment

    def raise_handler_error(self, msg):
        _ = self.ugettext
        raise JsonHandlerError(400, _(msg))

    @XBlock.json_handler
    def sync_runtime_info(self, data, suffix=''):
        _ = self.ugettext
        try:
            package_version = data['package_version']
            package_date = data['package_date']
        except KeyError:
            self.raise_handler_error("missing parameters.")

        if self.is_pkg_expired(package_date):
            return {'error': _('scorm package expired, refresh page to get new content.')}

        if package_version == SCORM_VERSION.V12:
            default = deepcopy(SCORM_12_RUNTIME_DEFAULT)
            default['cmi.core.student_id'] = str(self.runtime.user_id)
            default['cmi.core.student_name'] = User.objects.get(id=self.runtime.user_id).username
            if self.scorm_runtime_data.get('cmi.core.exit', None):
                if self.scorm_runtime_data.get('cmi.core.exit') == 'suspend':
                    default['cmi.core.entry'] = 'resume'
        elif package_version == SCORM_VERSION.V2004:
            default = deepcopy(SCORM_2004_RUNTIME_DEFAULT)
            default['cmi.learner_id'] = str(self.runtime.user_id)
            default['cmi.learner_name'] = User.objects.get(id=self.runtime.user_id).username
            if self.scorm_runtime_data.get('cmi.exit', None):
                if self.scorm_runtime_data.get('cmi.exit') == 'suspend':
                    default['cmi.entry'] = 'resume'
        else:
            self.raise_handler_error('error scorm package version')

        default['cmi.launch_data'] = self.scorm_launch_data
        data = dict(default, **self.scorm_runtime_data)
        return {"value": data}

    @XBlock.json_handler
    def scorm_get_value(self, data, suffix=''):
        _ = self.ugettext
        try:
            name = data['name']
            package_version = data['package_version']
            package_date = data['package_date']
        except KeyError:
            self.raise_handler_error("missing parameters.")

        if package_version == SCORM_VERSION.V12:
            default = SCORM_12_RUNTIME_DEFAULT.get(name, '')
            if name == 'cmi.core.student_id':
                default = str(self.runtime.user_id)
            elif name == 'cmi.core.student_name':
                user = User.objects.get(id=self.runtime.user_id)
                default = user.username
            elif name == 'cmi.core.entry':
                if self.scorm_runtime_data.get('cmi.core.exit', None):
                    if self.scorm_runtime_data.get('cmi.core.exit') == 'suspend':
                        default = 'resume'
        elif package_version == SCORM_VERSION.V2004:
            default = SCORM_2004_RUNTIME_DEFAULT.get(name, '')
            if name == 'cmi.learner_id':
                default = str(self.runtime.user_id)
            elif name == 'cmi.learner_name':
                user = User.objects.get(id=self.runtime.user_id)
                default = user.username
            elif name == 'cmi.entry':
                if self.scorm_runtime_data.get('cmi.exit', None):
                    if self.scorm_runtime_data.get('cmi.exit') == 'suspend':
                        default = 'resume'
        else:
            self.raise_handler_error('error scorm package version')

        if name == 'cmi.launch_data':
            default = self.scorm_launch_data

        if self.is_pkg_expired(package_date):
            return {'error': _('scorm package expired, refresh page to get new content.')}
        # logger.info('get_value: ' + str(self.scorm_runtime_data.get(name, default)))

        return {"value": self.scorm_runtime_data.get(name, default)}

    def is_pkg_expired(self, package_date):
        return self.scorm_pkg_modified and package_date and str2dt(package_date) < self.scorm_pkg_modified

    def is_runtime_data_expired(self, package_date):
        expired = False
        need_update = True
        if self.scorm_pkg_modified:
            if package_date and str2dt(package_date) < self.scorm_pkg_modified:
                # when user still visit one scorm, but new package uploaded
                # so, no update, only update when user next time visit new uploaded scorm
                expired = True
                need_update = False
            elif self.scorm_runtime_modified and self.scorm_runtime_modified < self.scorm_pkg_modified:
                # normal case
                expired = True
                need_update = True
        return expired, need_update

    @XBlock.json_handler
    def scorm_commit(self, data, suffix=''):

        package_date = data.pop('package_date', '')
        package_version = data.pop('package_version', '')
        expired, need_update = self.is_runtime_data_expired(package_date)
        if expired:
            self.scorm_runtime_data = {}
        if need_update:
            self.scorm_runtime_data.update(data)

        self.scorm_runtime_modified = timezone.now()

        self.update_scorm_status(data, package_version)
        return self.get_fields_data(True, 'scorm_status', 'scorm_score')

    @XBlock.json_handler
    def scorm_enforce_commit(self, data, suffix=''):

        package_date = data.pop('package_date', '')
        package_version = data.pop('package_version', '')
        expired, need_update = self.is_runtime_data_expired(package_date)
        if expired:
            self.scorm_runtime_data = {}
        if need_update:
            self.scorm_runtime_data.update(data)

        self.scorm_runtime_modified = timezone.now()

        self.update_scorm_status(data, package_version)
        return self.get_fields_data(True, 'scorm_status', 'scorm_score')

    @XBlock.handler
    def scorm_ios_commit(self, request, suffix=''):

        post_data = request.POST.copy()
        post_data.pop('csrfmiddlewaretoken', '')
        package_date = post_data.pop('package_date', '')
        package_version = post_data.pop('package_version', '')
        expired, need_update = self.is_runtime_data_expired(package_date)
        update_data = {}
        for x, y in six.iteritems(post_data):
            update_data[x] = y
        if expired:
            self.scorm_runtime_data = {}
        if need_update:
            self.scorm_runtime_data.update(update_data)

        self.scorm_runtime_modified = timezone.now()

        self.update_scorm_status(update_data, package_version)
        response_data = self.get_fields_data(True, 'scorm_status', 'scorm_score')
        return Response(json_body=response_data, content_type='application/json')

    @XBlock.handler
    def sync_score_value(self, request, suffix=''):
        """
        Fix double refresh bug cause of unexpected terminal action
        """
        score_value = self.get_fields_data(True, 'scorm_score')
        return Response(json_body=score_value, content_type='application/json')

    @staticmethod
    def extract_runtime_info_12(data):
        info = {'status': SCORM_STATUS.IN_PROGRESS}
        if 'cmi.core.score.raw' in data:
            score_raw = data.get('cmi.core.score.raw')
            info['raw'] = 0.0 if score_raw is None else float(score_raw)
            info['mini'] = float(data.get('cmi.core.score.min', 0.0))
            if 'cmi.core.score.max' in data:
                info['maxi'] = float(data.get('cmi.core.score.max'))
            else:
                info['maxi'] = 100.0 if info['raw'] > 1 else 1.0

        lesson_status = data.get('cmi.core.lesson_status', SCORM_STATUS.IN_PROGRESS)

        if lesson_status in ['passed', 'completed']:
            info['status'] = SCORM_STATUS.SUCCEED
        elif lesson_status == 'failed':
            info['status'] = SCORM_STATUS.FAILED

        # The `cmi.completion_status` is supported by scormV2004 standard only. But here we just add an additional support for scormV12
        # cmi.completion_status ("completed", "incomplete", "not attempted", "unknown", RW) Indicates whether the learner has completed the SCO
        lesson_status = data.get('cmi.completion_status')
        if lesson_status == 'completed':
            info['status'] = SCORM_STATUS.SUCCEED

        return info

    @staticmethod
    def extract_runtime_info_2004(data):
        info = {'status': SCORM_STATUS.IN_PROGRESS}
        if data.get('cmi.score.raw') and data.get('cmi.score.max') and data.get('cmi.score.min'):
            info['raw'] = float(data['cmi.score.raw'])
            info['maxi'] = float(data['cmi.score.max'])
            info['mini'] = float(data['cmi.score.min'])
        elif data.get('cmi.score.scaled'):
            info['raw'] = float(data['cmi.score.scaled'])
            info['maxi'] = 1.0
            info['mini'] = 0.0

        success_status = data.get('cmi.success_status', SCORM_STATUS.IN_PROGRESS)
        if success_status == 'passed':
            info['status'] = SCORM_STATUS.SUCCEED
        elif success_status == 'failed':
            info['status'] = SCORM_STATUS.FAILED

        # Doc: https://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/?utm_source=google&utm_medium=natural_search#section-2
        # cmi.completion_status ("completed", "incomplete", "not attempted", "unknown", RW) Indicates whether the learner has completed the SCO
        success_status = data.get('cmi.completion_status')
        if success_status == 'completed':
            info['status'] = SCORM_STATUS.SUCCEED

        return info

    def extract_runtime_info(self, data, version):
        if version == SCORM_VERSION.V12:
            return self.extract_runtime_info_12(data)
        if version == SCORM_VERSION.V2004:
            return self.extract_runtime_info_2004(data)

        self.raise_handler_error('error scorm pkg version')

    def update_scorm_status(self, data, version):

        info = self.extract_runtime_info(data, version)
        score = None
        if 'raw' in info:
            score = Score(raw_earned=(info['raw'] - info['mini']),
                          raw_possible=(info['maxi'] - info['mini']))

        if score:
            # log the data without suspend_data
            log_data = deepcopy(data)
            if log_data.get('cmi.suspend_data'):
                log_data.pop('cmi.suspend_data')
            logger.info("scorm_commit SCORE Usage: %s, User: %s, Data: %s",
                str(self.scope_ids.usage_id),
                self.runtime.user_id,
                log_data
            )

            if not self.has_submitted_answer() or self.allows_rescore():
                self.set_score(score)
                self._publish_grade(self.get_score())

                self.scorm_status = info['status']
            else:
                logger.info(
                    "refused to publish score {} for student id {} in {} [{}]".format(
                        score.raw_earned,
                        str(self.runtime.user_id),
                        str(self.scope_ids.usage_id),
                        data
                    )
                )

        if info['status'] == SCORM_STATUS.SUCCEED:

            # log the data without suspend_data
            log_data = deepcopy(data)
            if log_data.get('cmi.suspend_data'):
                log_data.pop('cmi.suspend_data')
            logger.info("scorm_commit SUCCEED Usage: %s, User: %s, Data: %s",
                str(self.scope_ids.usage_id),
                self.runtime.user_id,
                log_data
            )

            # Use runtime.publish so the completion event passes through the LMS
            # masquerade guard (module_render.py:522). The previous direct call to
            # BlockCompletion.objects.submit_batch_completion() bypassed that guard and
            # wrote a real BlockCompletion record for the student when an admin used
            # "View as" masquerade, causing completion_date without a grade.
            self.runtime.publish(self, 'completion', {'completion': 1.0})

            self.scorm_status = info['status']

    @XBlock.handler
    def ping(self, request, suffix=''):
        return Response(status=200)

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("ScormXBlock",
             """<vertical_demo>
                <scormxblock/>
                </vertical_demo>
             """),
        ]
