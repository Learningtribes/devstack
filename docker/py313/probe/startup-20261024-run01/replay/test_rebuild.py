"""Rebuild orchestration tests; no Docker daemon access."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import rebuild as replay_rebuild
from core import APP_SOURCE, APP_STATE
from test_core import example


class RebuildTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = example(Path(temporary.name))
        self.events = MagicMock()
        for target, label, kwargs in [
                ('rebuild.ownership', 'ownership', {}),
                ('rebuild.ensure_runtime_log_dirs', 'ensure_runtime_log_dirs', {}),
                ('rebuild.ensure_npm', 'ensure_npm', {}),
                ('rebuild.run_shell', 'run_shell', {}),
                ('rebuild.run', 'run', {}),
                ('rebuild.docker_exec', 'docker_exec', {'side_effect': lambda *a, **k: ['docker', 'exec', *a]}),
                ('rebuild.subprocess.run', 'subprocess_run',
                 {'return_value': MagicMock(returncode=0)})]:
            patcher = patch(target, **kwargs)
            self.events.attach_mock(patcher.start(), label)
            self.addCleanup(patcher.stop)

    def test_translations_runs_locale_static_for_both_systems(self):
        replay_rebuild.rebuild(self.config, 'translations')
        self.assertEqual(
            [call.args for call in self.events.run_shell.call_args_list],
            [(self.config, 'lms', '/startup/locale_static.py'),
             (self.config, 'cms', '/startup/locale_static.py')])
        self.events.ensure_runtime_log_dirs.assert_called_once_with(self.config)

    def test_assets_uses_fresh_xmodule_build_root_then_frontend(self):
        replay_rebuild.rebuild(self.config, 'assets')
        self.events.ensure_npm.assert_called_once_with(self.config)
        self.assertEqual(self.events.run_shell.call_args.args[:3],
                         (self.config, 'lms', '/startup/build_xmodule_assets.py'))
        build_root = self.events.run_shell.call_args.kwargs['extra_env']['BRINGUP_XMODULE_BUILD_ROOT']
        self.assertTrue(build_root.startswith(APP_STATE + '/xmodule-source-build-'))
        self.events.run.assert_called_once()
        self.assertIn('build_frontend.sh', str(self.events.docker_exec.call_args))

    def test_npm_only_ensures_node_modules(self):
        replay_rebuild.rebuild(self.config, 'npm')
        self.events.ensure_npm.assert_called_once_with(self.config)
        self.events.run_shell.assert_not_called()


class EnsureNpmTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = example(Path(temporary.name))

    def test_skips_npm_ci_when_webpack_exists(self):
        with patch('rebuild.subprocess.run', return_value=MagicMock(returncode=0)) as run, \
                patch('rebuild.run') as rebuild_run:
            replay_rebuild.ensure_npm(self.config)
        self.assertEqual(run.call_count, 1)
        self.assertIn(APP_SOURCE + '/node_modules/.bin/webpack', run.call_args.args[0])
        rebuild_run.assert_not_called()

    def test_runs_npm_ci_when_webpack_missing(self):
        probe = MagicMock(returncode=1)
        verify = MagicMock(returncode=0)
        with patch('rebuild.subprocess.run', side_effect=[probe, verify]) as run, \
                patch('rebuild.run') as rebuild_run, \
                patch('rebuild.docker_exec', return_value=['docker', 'exec', 'npm', 'ci']) as docker_exec:
            replay_rebuild.ensure_npm(self.config)
        rebuild_run.assert_called_once()
        self.assertEqual(docker_exec.call_args.args[1], 'npm')
        self.assertEqual(run.call_count, 2)


if __name__ == '__main__':
    unittest.main()
