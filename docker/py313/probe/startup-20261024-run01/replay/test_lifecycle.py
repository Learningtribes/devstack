"""Lifecycle start/stop orchestration tests; no Docker daemon access."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import lifecycle
from test_core import example


class EnsureRuntimeLogDirsTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = example(Path(temporary.name))

    def test_runs_mkdir_for_lms_and_cms_log_dirs(self):
        with patch('lifecycle.docker', return_value=MagicMock(returncode=0, stderr='', stdout='')) as docker:
            lifecycle.ensure_runtime_log_dirs(self.config)
        docker.assert_called_once_with(
            'exec', self.config['runtime_container'], 'mkdir', '-p',
            '/edx/var/log/lms', '/edx/var/log/cms')

    def test_nonzero_returncode_is_a_readable_error(self):
        with patch('lifecycle.docker',
                   return_value=MagicMock(returncode=1, stderr='permission denied\n', stdout='')):
            with self.assertRaisesRegex(SystemExit, r'Failed to create /edx/var/log/\{lms,cms\}: permission denied'):
                lifecycle.ensure_runtime_log_dirs(self.config)


class LifecycleStartTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = example(Path(temporary.name))
        self.startup = Path(temporary.name) / 'startup'
        self.startup.mkdir()
        for name in ('start_http.py', 'start_worker.py'):
            (self.startup / name).write_text('# fixture\n')
        self.core = MagicMock()
        self.core.environment.return_value = {'ENV': '1'}
        self.events = MagicMock()
        for target, label, kwargs in [
                ('lifecycle.classify', 'classify',
                 {'return_value': ([self.config['runtime_container']], [], [])}),
                ('lifecycle.docker', 'docker',
                 {'return_value': MagicMock(returncode=0, stdout='', stderr='')}),
                ('lifecycle.ensure_runtime_log_dirs', 'ensure_runtime_log_dirs', {}),
                ('lifecycle.subprocess.run', 'run',
                 {'return_value': MagicMock(returncode=0, stdout='', stderr='')}),
                ('lifecycle.hearts', 'hearts',
                 {'return_value': {'lms': 200, 'cms': 200}})]:
            patcher = patch(target, **kwargs)
            self.events.attach_mock(patcher.start(), label)
            self.addCleanup(patcher.stop)

    def test_start_ensures_log_dirs_when_runtime_is_owned(self):
        lifecycle.start(self.core, self.config, self.startup, 5, has_discovery=False)
        self.core.ownership.assert_called_once_with(self.config)
        self.events.ensure_runtime_log_dirs.assert_called_once_with(self.config)
        self.events.docker.assert_any_call('start', self.config['runtime_container'])

    def test_start_skips_log_dirs_when_runtime_is_absent(self):
        self.events.classify.return_value = ([], [], [self.config['runtime_container']])
        lifecycle.start(self.core, self.config, self.startup, 5, has_discovery=False)
        self.events.ensure_runtime_log_dirs.assert_not_called()


if __name__ == '__main__':
    unittest.main()
