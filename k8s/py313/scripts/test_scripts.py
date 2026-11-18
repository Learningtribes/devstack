"""Tests of the local scripts that need neither a cluster nor Docker.

    uv run --no-project --python 3.13 python -B -m unittest discover -s k8s/py313/scripts -p 'test_*.py' -v
"""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

import postprocess_config

HERE = Path(__file__).resolve().parent
SCRIPTS = ('up', 'status', 'smoke', 'down', 'gen-local-secrets', 'gen-local-config', 'setup-elasticsearch')


def env_json(system):
    return {
        'LMS_BASE': 'localhost:18000', 'CMS_BASE': 'localhost:18010', 'ALLOWED_HOSTS': ['localhost', 'localhost:18000'],
        'LOG_DIR': f'/edx/var/log/{system}', 'LOG_DESTINATION': 'file',
        'MEDIA_ROOT': '/edx/var/edxapp/media', 'DATA_DIR': '/edx/var/edxapp/data',
        'ELASTIC_SEARCH_CONFIG': [{'host': 'elasticsearch', 'port': 9200, 'use_ssl': True, 'verify_certs': True,
                                   'ca_certs': '/edx/app/edxapp/py313-config/es-ca.crt', 'http_auth': ['py313_search', 'x']}],
    }


def auth_json(system):
    data = {'SECRET_KEY': 'k', 'CELERY_BROKER_PASSWORD': 'p'}
    if system == 'lms':
        data['JWT_PRIVATE_SIGNING_KEY'] = 'pem'
    return data


class PostprocessTest(unittest.TestCase):
    def write(self, directory, mutate=None):
        for system in ('lms', 'cms'):
            env = env_json(system)
            if mutate:
                mutate(system, env)
            (directory / f'{system}.env.json').write_text(json.dumps(env))
            (directory / f'{system}.auth.json').write_text(json.dumps(auth_json(system)))

    def run_process(self, directory):
        with contextlib.redirect_stdout(io.StringIO()):
            return postprocess_config.process(directory, 'localhost:18000', 'localhost:18010',
                                              '/edx/app/edxapp/py313-config/es-ca.crt', 'py313_search')

    def test_log_destination_becomes_console_and_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.write(directory)
            self.assertEqual(self.run_process(directory), [])
            for system in ('lms', 'cms'):
                self.assertEqual(json.loads((directory / f'{system}.env.json').read_text())['LOG_DESTINATION'], 'console')
                self.assertEqual(stat.S_IMODE((directory / f'{system}.env.json').stat().st_mode), 0o600)

    def test_wildcard_host_or_plain_http_search_fails(self):
        def wildcard(system, env):
            env['ALLOWED_HOSTS'].append('*')

        def plain(system, env):
            env['ELASTIC_SEARCH_CONFIG'][0]['use_ssl'] = False
        for mutate in (wildcard, plain):
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                self.write(directory, mutate)
                self.assertTrue(self.run_process(directory), mutate.__name__)


class ContextGuardTest(unittest.TestCase):
    """Every script refuses to touch a cluster whose current context is not `orbstack`; the stub kubectl records any call."""

    def test_wrong_context_is_refused_before_any_cluster_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / 'bin'
            bin_dir.mkdir()
            log = Path(tmp) / 'calls.log'
            stub = bin_dir / 'kubectl'
            stub.write_text('#!/bin/sh\n'
                            f'if [ "$1 $2" = "config current-context" ]; then echo production-cluster; exit 0; fi\n'
                            f'echo "$@" >> {log}\nexit 0\n')
            stub.chmod(0o755)
            for name in SCRIPTS:
                env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', LOCAL_DIR=str(Path(tmp) / 'local'))
                env.pop('ALLOW_CONTEXT', None)
                result = subprocess.run([str(HERE / name)], env=env, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("expected 'orbstack'", result.stderr, name)
            self.assertFalse(log.exists(), 'a script called kubectl against the wrong context')

    def test_allow_context_override_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / 'bin'
            bin_dir.mkdir()
            stub = bin_dir / 'kubectl'
            stub.write_text('#!/bin/sh\nif [ "$1 $2" = "config current-context" ]; then echo other; exit 0; fi\nexit 1\n')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', ALLOW_CONTEXT='other')
            result = subprocess.run([str(HERE / 'status')], env=env, capture_output=True, text=True, timeout=60)
            self.assertNotIn("expected 'other'", result.stderr)

    def test_namespace_is_not_configurable(self):
        text = (HERE / 'lib.sh').read_text()
        self.assertIn('readonly NS=py313-prod-local', text)
        for name in SCRIPTS:
            self.assertNotIn('NS=', (HERE / name).read_text().replace('$NS', ''), name)

    def test_no_script_deletes_docker_objects_or_other_namespaces(self):
        forbidden = ('docker rm', 'docker rmi', 'docker volume', 'docker system', 'docker image prune', 'docker container prune',
                     'delete namespace kube', 'delete ns ')
        for name in (*SCRIPTS, 'lib.sh'):
            text = (HERE / name).read_text()
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f'{name}: {phrase}')
        down = (HERE / 'down').read_text()
        self.assertEqual(down.count('delete namespace'), 1)
        self.assertIn('delete namespace "$NS"', down)

    def test_scripts_are_executable_and_pass_bash_n(self):
        for name in (*SCRIPTS, 'lib.sh'):
            path = HERE / name
            if name != 'lib.sh':
                self.assertTrue(os.access(path, os.X_OK), name)
            subprocess.run(['bash', '-n', str(path)], check=True)


if __name__ == '__main__':
    unittest.main()
