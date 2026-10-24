"""
    When creating a course in Studio, it is possible to integrate content
    from external tools such as Genially, Articulate, Padlet ... and many more.
    Right now, you should copy and paste an iframe code or create it by
    yourself (in HTML format) on a text or Raw HTML component.

"""

import logging

from django.template import Context, Template
from django.utils.translation import gettext as _
import pkg_resources
from xblock.core import XBlock
from xblock.fields import Integer, String, Scope
from xblock.fragment import Fragment
from xblock.exceptions import JsonHandlerError
from xblockutils.studio_editable import StudioEditableXBlockMixin

from .config import SupportedExternalResources, SUPPORTED_EXTERNAL_RESOURCES


log = logging.getLogger(__name__)


class ExternalContentXBlock(StudioEditableXBlockMixin, XBlock):
    """XBlock module of External Web Content Editor / Publisher
    """

    display_name = String(
        help='The name of the component seen by the learners.',
        display_name='Display Name',
        default='External Web Content',      # name that appears in advanced settings studio menu
        scope=Scope.settings
    )

    iframe_url = String(
        display_name='iFrame Code',
        help='Paste here your iFrame Code from the authoring tool, {link_start}more...{link_end}',
        default="",
        scope=Scope.settings
    )

    has_author_view = True

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        res_str = pkg_resources.resource_string(__name__, path)
        return res_str if isinstance(res_str, str) else res_str.decode("utf8")

    def render_template(self, template_path, context=None):
        """Evaluate a template by resource path, applying the provided context"""
        SupportedExternalResources.assign_externality_handle(self)

        template = Template(self.resource_string(template_path))

        return template.render(Context(context or {}))

    def xblock_field_list(self, field_names):
        """Handy helper for getting a dictionary of fields"""
        xblock = self

        return [
            {
                'name': field,
                'value': getattr(xblock, field),
                'help': getattr(xblock.__class__, field).help,
                'display_name': getattr(xblock.__class__, field).display_name,
                'type': type(getattr(xblock.__class__, field)).__name__
            } for field in field_names
        ]

    def student_view(self, context=None):
        """The primary view of the ExternalContentXBlock, shown to students when viewing courses.
        """
        frag = Fragment()
        frag.add_content(
            self.render_template(
                'templates/html/externality.html',
                {
                    'self': self,
                    'fields': self.xblock_field_list(['display_name', 'iframe_url']),
                    'display_name': self.display_name,
                }
            )
        )
        frag.add_css(self.resource_string('static/css/externality.css'))
        # Inject js Script to <head> in file: cms/static/js/views/xblock.js#L218
        frag.add_javascript(self.resource_string('static/js/src/externality.js'))
        frag.initialize_js('ExternalContentXBlock')

        return frag

    def author_view(self, context=None):
        """View of Studio Courses page"""
        frag = Fragment()
        frag.add_content(
            self.render_template(
                'templates/html/author_externality.html',
                {'self': self, 'fields': self.xblock_field_list(['display_name', 'iframe_url'])}
                if self.iframe_url else {
                    'self': self,
                    'external_resources': SUPPORTED_EXTERNAL_RESOURCES,
                    'usd_svg': self.resource_string('static/images/dollar.svg')
                }
            )
        )
        frag.add_css(self.resource_string('static/css/externality.css'))
        # Inject js Script to <head> in file: cms/static/js/views/xblock.js#L218
        frag.add_javascript(self.resource_string('static/js/src/externality.js'))
        frag.initialize_js('ExternalContentXBlock')

        return frag

    def studio_view(self, context=None):
        """
        The studio view of the ExternalContentXBlock, with form
        """
        frag = Fragment()
        frag.add_content(
            self.render_template(
                'templates/html/studio-externality.html',
                {'self': self, 'fields': self.xblock_field_list(['display_name', 'iframe_url'])}
            )
        )
        frag.add_css(self.resource_string('static/css/externality.css'))
        frag.add_javascript(self.resource_string('static/js/src/studio-externality.js'))
        frag.initialize_js('StudioExternalContentXBlock')

        return frag

    @XBlock.json_handler
    def publish_completion(self, data, dispatch):  # pylint: disable=unused-argument
        """
        Entry point for completion for student_view.
        Parameters:
            data: JSON dict:
                key: "completion"
                value: float in range [0.0, 1.0]
            dispatch: Ignored.
        Return value: JSON response (200 on success, 400 for malformed data)
        """
        completion_service = self.runtime.service(self, 'completion')

        if completion_service is None:
            raise JsonHandlerError(500, u"No completion service found")
        elif not completion_service.completion_tracking_enabled():
            raise JsonHandlerError(404, u"Completion tracking is not enabled and API calls are unexpected")
        if not isinstance(data['completion'], (int, float)):
            message = u"Invalid completion value {}. Must be a float in range [0.0, 1.0]"
            raise JsonHandlerError(400, message.format(data['completion']))
        elif not 0.0 <= data['completion'] <= 1.0:
            message = u"Invalid completion value {}. Must be in range [0.0, 1.0]"
            raise JsonHandlerError(400, message.format(data['completion']))

        self.runtime.publish(self, "completion", data)

        return {'result': 'ok'}

    @XBlock.json_handler
    def studio_submit(self, submissions, suffix=''):
        if submissions['iframe_url']== "":
            response = {
                'result': 'error',
                'message': 'You should give a valid URL'
            }
        else:
            log.info(u'Received submissions: {}'.format(submissions))
            self.display_name = submissions['display_name']
            self.iframe_url = submissions['iframe_url']
            response = {
                'result': 'success',
            }
        return response

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("ExternalContentXBlock",
             """<externality/>
             """),
            ("Multiple ExternalContentXBlock",
             """<vertical_demo>
                <externality/>
                <externality/>
                <externality/>
                </vertical_demo>
             """),
        ]
