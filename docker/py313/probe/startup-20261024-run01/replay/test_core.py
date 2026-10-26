"""Resource collision and output reservation tests; no Docker daemon mutations."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import run as replay_run
from core import (SECRET_KEYS, SERVICES, capture, check_conflicts, environment, load_config,
                  physical_names, secret_values, source_repository_roots,
                  validate_path_isolation)


def example(root, run_id='run44'):
    prefix = 'py313-replay-' + run_id
    return dict(run_id=run_id, evidence_dir=str(root / ('evidence-' + run_id)), export_dir=str(root / ('export-' + run_id)),
        platform_repo=str(root / 'platform'), platform_commit='a' * 40, devstack_repo=str(root / 'devstack'),
        devstack_commit='b' * 40, theme_commit='c' * 40, runtime_container=prefix + '-runtime',
        runtime_volume=prefix + '-runtime-data', network=prefix + '-network',
        services={name: {'container': prefix + '-' + name, **({'volume': prefix + '-' + name + '-data'}
            if name in ('mysql', 'mongo', 'rabbitmq', 'elasticsearch') else {})} for name in SERVICES},
        images={name: ('sha256:' + 'a' * 64 if name == 'runtime' else name + ':test') for name in (*SERVICES, 'runtime')},
        lms_port=18240, cms_port=18250, database='py313_rebuild_' + run_id, test_database='py313_rebuild_' + run_id + '_test',
        mongo_database='py313_mongo_' + run_id, cache_prefix='py313_cache_' + run_id, es_prefix='py313_es_' + run_id + '_',
        queue_prefix='py313_queue_' + run_id, course_key='course-v1:PY313+Replay_' + run_id + '+2026',
        secret_env=str(root / ('secret-' + run_id + '.env')), credentials_file=str(root / 'credentials.json'), jwt_file=str(root / 'jwt.pem'))


class ContractTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = example(self.root)
        Path(self.config['platform_repo']).mkdir()
        Path(self.config['devstack_repo']).mkdir()
        self.path = self.root / 'config.json'
        self.write()
        self.secret = '1' * 48
        p = Path(self.config['secret_env'])
        p.write_text(''.join(key + '=' + self.secret + '\n' for key in SECRET_KEYS))
        p.chmod(0o600)
        for key, content in [('credentials_file', json.dumps({'staff': {'password': 'fixture-password'}})), ('jwt_file', 'fixture-private-material')]:
            p = Path(self.config[key])
            p.write_text(content)
            p.chmod(0o600)

    def write(self):
        self.path.write_text(json.dumps(self.config))

    def test_explicit_config_and_empty_inventory(self):
        self.assertEqual(load_config(self.path), self.config)
        check_conflicts(self.config, {'containers': [], 'volumes': [], 'networks': []})
        second = example(self.root, 'run45')
        self.assertFalse(set(physical_names(self.config)) & set(physical_names(second)))

    def test_output_paths_cannot_overlap_source_repos(self):
        for key in ('evidence_dir', 'export_dir', 'secret_env'):
            with self.subTest(path=key):
                self.config = example(self.root)
                self.config[key] = str(Path(self.config['platform_repo']) / ('nested-' + key))
                self.write()
                with self.assertRaisesRegex(ValueError, key + ' must be outside platform_repo'):
                    load_config(self.path)

    def test_output_paths_resolve_symlinked_source_aliases(self):
        alias = self.root / 'platform-alias'
        alias.symlink_to(self.config['platform_repo'], target_is_directory=True)
        self.config['evidence_dir'] = str(alias / 'nested-evidence')
        self.write()
        with self.assertRaisesRegex(ValueError, 'evidence_dir must be outside platform_repo'):
            load_config(self.path)

    def test_protected_inputs_cannot_overlap_outputs_but_may_be_in_checkout(self):
        self.config['credentials_file'] = str(Path(self.config['evidence_dir']) / 'credentials.json')
        self.write()
        with self.assertRaisesRegex(ValueError, 'paths must be disjoint after resolution'):
            load_config(self.path)
        self.config = example(self.root)
        self.config['credentials_file'] = str(Path(self.config['platform_repo']) / 'credentials.json')
        self.config['jwt_file'] = str(Path(self.config['platform_repo']) / 'jwt.pem')
        self.write()
        self.assertEqual(load_config(self.path), self.config)

    def test_output_path_cannot_be_an_ancestor_of_a_source_repo(self):
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        external_root = Path(external.name)
        self.config['evidence_dir'] = str(self.root)
        self.config['export_dir'] = str(external_root / 'export')
        self.config['secret_env'] = str(external_root / 'secret.env')
        self.config['credentials_file'] = str(external_root / 'credentials.json')
        self.config['jwt_file'] = str(external_root / 'jwt.pem')
        self.write()
        with self.assertRaisesRegex(ValueError, 'evidence_dir must be outside platform_repo'):
            load_config(self.path)

    def test_actual_repository_root_is_checked_for_path_overlap(self):
        roots = {'platform': Path(self.config['platform_repo']).parent.resolve(),
                 'devstack': Path(self.config['devstack_repo']).resolve()}
        with self.assertRaisesRegex(ValueError, 'evidence_dir must be outside platform_repo'):
            validate_path_isolation(self.config, roots)

    def test_configured_repo_must_be_checkout_root(self):
        with patch('core.subprocess.check_output', return_value=str(self.root)):
            with self.assertRaisesRegex(ValueError, 'platform_repo must name the Git checkout root'):
                source_repository_roots(self.config)

    def test_every_existing_physical_resource_rejected(self):
        for resource in physical_names(self.config):
            for kind in ('containers', 'volumes', 'networks'):
                with self.subTest(resource=resource, kind=kind):
                    inventory = {'containers': [], 'volumes': [], 'networks': []}
                    inventory[kind] = [resource]
                    with self.assertRaisesRegex(ValueError, 'existing resources'):
                        check_conflicts(self.config, inventory)

    def test_required_fields_and_run_namespace(self):
        del self.config['runtime_container']
        self.write()
        with self.assertRaisesRegex(ValueError, 'missing='):
            load_config(self.path)
        self.config = example(self.root)
        self.config['database'] = 'py313_rebuild_old'
        self.write()
        with self.assertRaisesRegex(ValueError, 'contain run_id'):
            load_config(self.path)

    def test_protected_env_cannot_override_namespace(self):
        path = Path(self.config['secret_env'])
        with path.open('a') as stream:
            stream.write('PY313_DATABASE_NAME=old-database\n')
        with self.assertRaisesRegex(ValueError, 'namespaces belong in config'):
            secret_values(self.config)

    def test_prior_environment_is_not_a_target_fallback(self):
        with patch.dict(os.environ, {'PY313_RUNTIME_CONTAINER': 'old-container', 'PY313_DATABASE_NAME': 'old-database'}):
            env = environment(self.config)
        self.assertEqual(env['PY313_RUNTIME_CONTAINER'], self.config['runtime_container'])
        self.assertEqual(env['PY313_DATABASE_NAME'], self.config['database'])
        self.assertEqual(env['PY313_ACCEPTANCE_COURSE_ID'], self.config['course_key'])

    def test_duplicate_label_rejected_before_second_side_effect_and_secrets_redacted(self):
        Path(self.config['evidence_dir']).mkdir()
        effect = self.root / 'effect'
        command = [sys.executable, '-c',
                   'from pathlib import Path;import os;Path(' + repr(str(effect)) + ').write_text("once");'
                   'print(os.environ["PY313_MYSQL_PASSWORD"])']
        with contextlib.redirect_stdout(io.StringIO()):
            capture(self.config, 'mutation', command)
        effect.write_text('retained')
        with self.assertRaises(FileExistsError):
            capture(self.config, 'mutation', command)
        self.assertEqual(effect.read_text(), 'retained')
        outputs = Path(self.config['evidence_dir'])
        self.assertNotIn(self.secret, (outputs / 'mutation.txt').read_text())
        self.assertIn('<redacted>', (outputs / 'mutation.txt').read_text())
        self.assertEqual(len((outputs / 'commands.jsonl').read_text().splitlines()), 1)

    def test_install_captures_installed_source_identity_after_install(self):
        with patch.object(replay_run, 'ownership') as ownership, \
             patch.object(replay_run, 'capture') as capture, \
             patch.object(replay_run, 'docker_exec', return_value=['docker', 'exec', 'identity']) as docker_exec:
            replay_run.install(self.config)
        self.assertEqual([call.args[1] for call in capture.call_args_list], [
            'input-preflight', 'install', 'installed-source-identity', 'installed-source-report'])
        docker_exec.assert_has_calls([
            unittest.mock.call(self.config, '/runtime/venv/bin/python', '/startup/replay/verify_installed_identity.py'),
            unittest.mock.call(self.config, 'cat', '/runtime/installed-input-identity.json')])
        self.assertEqual(capture.call_args_list[-1].kwargs, {'show_output': False})
        ownership.assert_called_once_with(self.config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
