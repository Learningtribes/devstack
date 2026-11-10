"""Interactive runtime shell tests; no Docker daemon access."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import shell as replay_shell
from core import SECRET_KEYS, docker_exec
from test_core import example


class ShellTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.config = example(root)
        Path(self.config['platform_repo']).mkdir()
        Path(self.config['devstack_repo']).mkdir()
        self.path = root / 'config.json'
        self.path.write_text(json.dumps(self.config))
        self.secret = '2' * 48
        Path(self.config['secret_env']).write_text(''.join(key + '=' + self.secret + '\n' for key in SECRET_KEYS))
        Path(self.config['secret_env']).chmod(0o600)
        self.ownership = patch('core.ownership')
        self.ownership_mock = self.ownership.start()
        self.addCleanup(self.ownership.stop)
        terminal = patch.dict(os.environ, {'TERM': 'xterm-fixture'})
        terminal.start()
        self.addCleanup(terminal.stop)

    def test_interactive_argv_allocates_tty_and_forwards_terminal_by_name(self):
        argv = docker_exec(self.config, 'bash', settings='startup_lms', interactive=True)
        self.assertEqual(argv[:5], ['docker', 'exec', '-it', '-w', '/runtime/platform-source'])
        self.assertIn('DJANGO_SETTINGS_MODULE=startup_lms', argv)
        self.assertEqual(argv[argv.index('TERM') - 1], '-e')
        self.assertEqual(argv[-2:], [self.config['runtime_container'], 'bash'])
        self.assertNotIn('xterm-fixture', argv)
        self.ownership_mock.assert_called_once_with(self.config)

    def test_shell_env_lets_paver_run_without_prereqs_and_reach_the_unauthenticated_test_mongo(self):
        argv = replay_shell.command(self.config, 'lms')
        env_args = argv[argv.index('env') + 1:argv.index('bash')]
        for assignment in ('TESTING=True', 'NO_PREREQ_INSTALL=True', 'SKIP_NPM_INSTALL=True',
                           'EDXAPP_TEST_MONGO_HOST=mongo', 'EDXAPP_TEST_MONGO_PORT=27018',
                           'NODE_OPTIONS=--max-old-space-size=2048', 'PAVER_DEVSTACK_SETTINGS=devstack_local'):
            self.assertIn(assignment, env_args)
        self.assertIn('PYTHONPATH=/startup/settings:/runtime/platform-source/ci/py313/test-stubs', env_args)

    def test_test_mongo_is_started_once_and_waited_for(self):
        listening = iter([False, False, True])
        with patch.object(replay_shell, 'test_mongo_listening', side_effect=lambda c: next(listening)), \
                patch.object(replay_shell.subprocess, 'run') as run, patch.object(replay_shell.time, 'sleep'):
            replay_shell.ensure_test_mongo(self.config)
        commands = [call.args[0] for call in run.call_args_list]
        mongo = self.config['services']['mongo']['container']
        self.assertEqual(commands[0], ['docker', 'exec', mongo, 'mkdir', '-p', '/tmp/py313-test-mongo'])
        self.assertEqual(commands[1][:4], ['docker', 'exec', '-d', mongo])
        self.assertIn('27018', commands[1])

    def test_asset_tools_are_on_the_path_and_npx_is_linked_idempotently(self):
        self.assertIn('/runtime/platform-source/node_modules/.bin', replay_shell.RUNTIME_PATH.split(':'))
        with patch.object(replay_shell.subprocess, 'run') as run:
            replay_shell.ensure_npx(self.config)
        (argv,), kwargs = run.call_args
        self.assertEqual(argv[:3], ['docker', 'exec', self.config['runtime_container']])
        self.assertIn('test -e /usr/local/bin/npx ||', argv[-1])
        self.assertIn('npx-cli.js', argv[-1])
        self.assertTrue(kwargs['check'])
        self.ownership_mock.assert_called_once_with(self.config)

    def test_running_test_mongo_is_left_alone(self):
        with patch.object(replay_shell, 'test_mongo_listening', return_value=True), \
                patch.object(replay_shell.subprocess, 'run') as run:
            replay_shell.ensure_test_mongo(self.config)
        run.assert_not_called()

    def test_live_platform_run_uses_the_same_process_root(self):
        self.config['platform_mount'] = 'live'
        argv = docker_exec(self.config, 'true')
        self.assertEqual(argv[:4], ['docker', 'exec', '-w', '/runtime/platform-source'])

    def test_non_interactive_argv_is_unchanged(self):
        argv = docker_exec(self.config, 'true', settings='startup_cms')
        self.assertNotIn('-it', argv)
        self.assertNotIn('TERM', argv)
        self.assertEqual(argv[:4], ['docker', 'exec', '-w', '/runtime/platform-source'])
        self.assertNotIn('-d', docker_exec(self.config, 'true'))
        self.assertEqual(docker_exec(self.config, 'true', detached=True)[:3], ['docker', 'exec', '-d'])

    def test_interactive_and_detached_are_rejected_before_any_docker_call(self):
        with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
            docker_exec(self.config, 'bash', detached=True, interactive=True)
        self.ownership_mock.assert_not_called()

    def run_main(self, *arguments):
        with patch.object(sys, 'argv', ['shell.py', *arguments]), \
                patch.object(replay_shell, 'ensure_test_mongo') as ensure, \
                patch.object(replay_shell, 'ensure_npx') as npx, \
                patch.object(replay_shell.os, 'execvpe') as execvpe:
            replay_shell.main()
        self.ensure_mock = ensure
        self.npx_mock = npx
        return execvpe

    def test_main_execs_bash_in_runtime_with_system_settings(self):
        for system in ('lms', 'cms'):
            with self.subTest(system=system):
                execvpe = self.run_main('--config', str(self.path), system)
                (program, argv, env), _ = execvpe.call_args
                self.assertEqual(program, 'docker')
                self.assertIn('-it', argv)
                self.assertIn('DJANGO_SETTINGS_MODULE=startup_' + system, argv)
                self.assertEqual(argv[argv.index(self.config['runtime_container']) + 1:][:2],
                                 ['env', 'PATH=' + replay_shell.RUNTIME_PATH])
                self.assertEqual(argv[-1], 'bash')
                self.ensure_mock.assert_called_once_with(self.config)
                self.npx_mock.assert_called_once_with(self.config)
                self.assertTrue(replay_shell.RUNTIME_PATH.startswith('/runtime/venv/bin:'))
                self.assertEqual(env['TERM'], 'xterm-fixture')

    def test_secret_values_reach_docker_only_through_the_environment(self):
        execvpe = self.run_main('--config', str(self.path), 'lms')
        (_, argv, env), _ = execvpe.call_args
        self.assertFalse([item for item in argv if self.secret in item])
        self.assertEqual(env['PY313_MYSQL_PASSWORD'], self.secret)
        self.assertIn('PY313_MYSQL_PASSWORD', argv)

    def test_ownership_failure_prevents_exec(self):
        self.ownership_mock.side_effect = ValueError('Runtime does not belong to this exact replay configuration')
        with self.assertRaises(ValueError):
            self.run_main('--config', str(self.path), 'lms')

    def test_test_mongo_failure_prevents_exec(self):
        with patch.object(sys, 'argv', ['shell.py', '--config', str(self.path), 'lms']), \
                patch.object(replay_shell, 'ensure_test_mongo', side_effect=SystemExit('no mongo')), \
                patch.object(replay_shell.os, 'execvpe') as execvpe, self.assertRaises(SystemExit):
            replay_shell.main()
        execvpe.assert_not_called()

    def test_system_and_config_are_required_and_validated(self):
        for arguments in (['--config', str(self.path), 'studio'], ['--config', str(self.path)], ['lms']):
            with self.subTest(arguments=arguments), patch.object(replay_shell.os, 'execvpe') as execvpe, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                with patch.object(sys, 'argv', ['shell.py', *arguments]):
                    replay_shell.main()
            self.assertEqual(raised.exception.code, 2)
            execvpe.assert_not_called()
        self.ownership_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
