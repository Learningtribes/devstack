"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources

from xblock.core import XBlock
from xblock.fields import Scope, Integer, String, Boolean
from xblock.fragment import Fragment
from xblock.exceptions import JsonHandlerError

from django.utils.translation import gettext as _
from django.template import Context, Template

from .utils import render_template, xblock_field_list

import logging
log = logging.getLogger(__name__)

class IframeWithAnonymousIDXBlock(XBlock):
    """
    XBlock displaying an iframe, with an anonymous ID passed in argument
    """

    # Fields are defined on the class. You can access them in your code as
    # self.<fieldname>.

    # URL format :
    # {iframe_url}

    display_name = String(
        help=_("The name of the component seen by the learners."),
        display_name=_("Component Display Name"),
        default=_("iFrame"),  # name that appears in advanced settings studio menu
        scope=Scope.user_state
    )

    iframe_url = String(
        display_name=_("iFrame URL"),
        help=_("Don't forget the leading protocol (http:// or https://) and the path, https://yoururl.com/path is correct, for example."),
		default="",
        scope=Scope.settings
    )

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self, context=None):
        """
        The primary view of the IframeWithAnonymousIDXBlock, shown to students
        when viewing courses.
        """

        student_id = self.xmodule_runtime.anonymous_student_id
        # student_id will be "student" if called from the Studio

        new_iframe_url = format(self.iframe_url)

        self.display_name = new_iframe_url

        context = {
            'self': self,
            'iframe_url': new_iframe_url,
            'is_in_studio': student_id == 'student'
        }

        frag = Fragment()
        frag.add_content(render_template('/templates/html/iframe.html', context))
        frag.add_css(self.resource_string("static/css/iframe.css"))
        frag.add_javascript(self.resource_string("static/js/src/iframe.js"))
        frag.initialize_js('IframeWithAnonymousIDXBlock')
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
        return {"result": "ok"}

    def studio_view(self, context=None):
        """
        The studio view of the IframeWithAnonymousIDXBlock, with form
        """
        context = {
            'self': self,
            'fields': xblock_field_list(self, [ "iframe_url" ])
        }

        frag = Fragment()
        frag.add_content(render_template('/templates/html/iframe-edit.html', context))
        frag.add_javascript(self.resource_string("static/js/src/iframe-edit.js"))
        frag.initialize_js('IframeWithAnonymousIDXBlock')
        return frag

    @XBlock.json_handler
    def studio_submit(self, submissions, suffix=''):
        if submissions['iframe_url']== "":
            response = {
                'result': 'error',
                'message': 'You should give a valid URL'
            }
        else:
            log.info(u'Received submissions: {}'.format(submissions))
            self.iframe_url = submissions['iframe_url']
            response = {
                'result': 'success',
            }
        return response

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("IframeWithAnonymousIDXBlock",
             """
			 """),
        ]
