"""Learning By Mooc Done XBlock"""

import pkg_resources

from xblock.core import XBlock
from xblock.fields import String, Scope, Dict, Boolean, Float, DateTime
from xblock.scorable import Score

from xblock.fragment import Fragment
from django.utils.translation import gettext as _
from xblockutils.studio_editable import StudioEditableXBlockMixin
try:
    from xmodule.progress import Progress
except ImportError:
    pass
from .mixins import ScorableXBlockMixin


@XBlock.needs('i18n', 'user')
class LbmDoneXBlock(StudioEditableXBlockMixin, ScorableXBlockMixin, XBlock):
    """
    Shows a toggle which lets learners mark a sequence as done.
    """

    display_name = String(
        default=_("Check Button"),
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Display Name"),
        help=_("Display name for this module"),
    )

    due = DateTime(
        default="2000-01-01T00:00:00.00",
        scope=Scope.settings,
        enforce_type=True,
        display_name=_("Due Date"),
        help=_("Due Date"),
    )

    icon_class = String(
        default='other',
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

    done = Boolean(
        scope=Scope.user_state,
        default=False
    )
    has_score = True
    editable_fields = ('display_name', 'weight', 'due', 'icon_class')

    def _create_score(self, earn):
        return Score(raw_possible=self.max_score(), raw_earned=earn)

    # region Runtime functions
    def max_score(self):
        return 1.0

    def allows_rescore(self):
        return True

    def set_score(self, score):
        self.done = True

    def get_score(self):
        return self._create_score(self.max_score()) if self.done else self._create_score(0)

    def calculate_score(self):
        return self.get_score()

    def has_submitted_answer(self):
        return self.done

    def get_progress(self):
        pg = self.max_score() if self.done else 0
        return Progress(pg, 1)

    # endregion



    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self, context=None):
        """
        LMS view, displayed to the student
        """
        # Load the HTML fragment from within the package and fill in the template
        html = self.resource_string("static/html/lbmdonexblock.html")
        frag = Fragment(html.format(done=self.done, button_text=_("Done")))

        # Load the CSS fragment
        frag.add_css(self.resource_string("static/css/lbmdonexblock.css"))

        # Load the JavaScript fragment
        frag.add_javascript(self.resource_string("static/js/src/lbmdonexblock.js"))
        frag.initialize_js('LbmDoneXBlock', {'done': self.done})

        return frag

    # def studio_view(self, context=None):
    #     """
    #     Studio view accessed when the instructor edits the component
    #     """
    #
    #     # Load the HTML fragment from within the package and fill in the template
    #     html = self.resource_string("static/html/lbmdonexblock_edit.html")
    #     frag = Fragment(html.format(no_edit_text=_("This XBlock has no editable field.")))
    #
    #     # Load the CSS fragment
    #     frag.add_css(self.resource_string("static/css/lbmdonexblock.css"))
    #
    #     return frag

    @XBlock.json_handler
    def toggle_button(self, data, suffix=''):
        """
        Ajax call when the button is clicked. Input is a JSON dictionary
        with one boolean field: `done`. This will save this in the
        XBlock field, and then issue an appropriate grade.
        """
        return_done = not self.done
        self.done = not self.done
        score = self.get_score()
        self._publish_grade(score)
        self.done = return_done
        completion = 1.0 if return_done else 0.0
        completion_data = {'completion': completion}
        self.runtime.publish(self, "completion", completion_data)
        return {'done': return_done}

    # Change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("LbmDoneXBlock",
             """<lbmdonexblock/>
             """),
        ]
