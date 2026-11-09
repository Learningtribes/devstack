"""Restart orchestration tests; no Docker daemon access."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import restart as replay_restart
from core import STARTUP_REL
from test_core import example


class RestartTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = example(Path(temporary.name))
        self.events = MagicMock()
        for target, label, kwargs in [
                ('restart.ownership', 'ownership', {}),
                ('restart.environment', 'environment', {'return_value': {'ENV': '1'}}),
                ('restart.wait_for_heartbeats', 'wait_for_heartbeats', {'return_value': {'lms': 200, 'cms': 200}}),
                ('restart.subprocess.run', 'run', {})]:
            patcher = patch(target, **kwargs)
            self.events.attach_mock(patcher.start(), label)
            self.addCleanup(patcher.stop)

    def test_restarts_runtime_then_starts_http_and_workers_for_both_systems(self):
        replay_restart.restart(self.config, 5)
        names = [call[0] for call in self.events.mock_calls]
        self.assertEqual(names[:2], ['ownership', 'run'])
        self.assertEqual(self.events.run.call_args_list[0].args[0], ['docker', 'restart', self.config['runtime_container']])
        startup = Path(self.config['export_dir']) / 'devstack' / STARTUP_REL
        started = [(Path(call.args[0][2]).name, call.args[0][3]) for call in self.events.run.call_args_list[1:]]
        self.assertEqual(started, [('start_http.py', 'lms'), ('start_http.py', 'cms'),
                                   ('start_worker.py', 'lms'), ('start_worker.py', 'cms')])
        self.assertTrue(all(call.args[0][2].startswith(str(startup)) for call in self.events.run.call_args_list[1:]))
        self.assertEqual(names[-1], 'wait_for_heartbeats')

    def test_failed_heartbeat_is_an_error(self):
        self.events.wait_for_heartbeats.return_value = {'lms': 200, 'cms': 502}
        with self.assertRaisesRegex(SystemExit, 'Heartbeat failed'):
            replay_restart.restart(self.config, 5)


if __name__ == '__main__':
    unittest.main()
