"""Target Python 3.13 regressions for registered LT package resources/sessions."""
import copy
import unittest

from externality.externality import ExternalContentXBlock
from iframe.utils import load_resource, render_template
from ilt.ilt import sorted_sessions


class LTCompatibilityTests(unittest.TestCase):
    def test_empty_and_counter_only_sessions(self):
        self.assertEqual(sorted_sessions({}), [])
        self.assertEqual(sorted_sessions({'counter': 3}), [])

    def test_session_order_and_counter_do_not_mutate_input(self):
        sessions = {
            'counter': 2,
            'later': {'start_at': '2026-12-03T12:00'},
            'earlier': {'start_at': '2026-12-01T12:00'},
        }
        before = copy.deepcopy(sessions)
        self.assertEqual([key for key, _ in sorted_sessions(sessions)], ['earlier', 'later'])
        self.assertEqual(sessions, before)

    def test_real_packaged_resources_are_text(self):
        self.assertIsInstance(load_resource('/templates/html/iframe.html'), str)
        self.assertIn('iframe', render_template('/templates/html/iframe.html'))
        resource = ExternalContentXBlock.resource_string(None, 'static/css/externality.css')
        self.assertIsInstance(resource, str)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(LTCompatibilityTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful(), 'LT target runtime regression failed'
