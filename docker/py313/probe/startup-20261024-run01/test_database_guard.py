"""Stdlib-only checks for the replay database name guard."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent / 'settings'))
from database_guard import is_replay_database  # noqa: E402


class DatabaseGuardTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('PY313_ADOPTED_DATABASE', None)

    def test_replay_prefixes_pass_and_others_fail(self):
        self.assertTrue(is_replay_database('py313_rebuild_run1'))
        self.assertTrue(is_replay_database('py313_startup_run1'))
        self.assertFalse(is_replay_database('stage-python3_edxapp'))
        self.assertTrue(is_replay_database('py313_x', ('py313_',)))

    def test_adopted_database_matches_only_the_exact_name(self):
        os.environ['PY313_ADOPTED_DATABASE'] = 'stage-python3_edxapp'
        self.assertTrue(is_replay_database('stage-python3_edxapp'))
        self.assertFalse(is_replay_database('stage-python3_edxapp_csmh'))
        self.assertFalse(is_replay_database('stage-python3'))

    def test_empty_adoption_never_matches(self):
        os.environ['PY313_ADOPTED_DATABASE'] = ''
        self.assertFalse(is_replay_database(''))


if __name__ == '__main__':
    unittest.main()
