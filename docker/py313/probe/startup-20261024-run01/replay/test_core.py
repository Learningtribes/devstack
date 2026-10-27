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
import audit_and_collect
from provision_acceptance import provision
from core import (SECRET_KEYS, SERVICES, capture, check_conflicts, environment, load_config,
                  physical_names, secret_values, source_repository_roots,
                  validate_path_isolation, validate_selected_image, config_hash, read_json,
                  IMAGE_LOCK_PATH, image_reference_parts, validate_image_lock, validate_network_subnet)


def example(root, run_id='run44'):
    prefix = 'py313-replay-' + run_id
    return dict(run_id=run_id, evidence_dir=str(root / ('evidence-' + run_id)), export_dir=str(root / ('export-' + run_id)),
        platform_repo=str(root / 'platform'), platform_commit='a' * 40, devstack_repo=str(root / 'devstack'),
        devstack_commit='b' * 40, theme_commit='c' * 40, runtime_container=prefix + '-runtime',
        runtime_volume=prefix + '-runtime-data', network=prefix + '-network', network_subnet='10.254.44.0/24',
        services={name: {'container': prefix + '-' + name, **({'volume': prefix + '-' + name + '-data'}
            if name in ('mysql', 'mongo', 'rabbitmq', 'elasticsearch') else {})} for name in SERVICES},
        images={**{name: record['reference'] for name, record in
                   read_json(IMAGE_LOCK_PATH)['services'].items()},
                'runtime': 'sha256:' + 'a' * 64},
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

    def test_generated_search_service_uses_bounded_heap(self):
        document = replay_run.compose(self.config)
        self.assertEqual(
            document['services']['elasticsearch']['environment']['ES_JAVA_OPTS'],
            '-Xms256m -Xmx256m',
        )

    def test_network_subnet_requires_private_ipv4_slash_24_and_rejects_overlap(self):
        self.assertEqual(validate_network_subnet('10.254.44.0/24'), '10.254.44.0/24')
        with self.assertRaisesRegex(ValueError, 'private IPv4 /24'):
            validate_network_subnet('192.168.0.0/23')
        with self.assertRaisesRegex(ValueError, 'private IPv4 /24'):
            validate_network_subnet('203.0.113.0/24')
        with self.assertRaisesRegex(ValueError, 'overlaps an existing Docker network'):
            validate_network_subnet('10.254.44.0/24', ['10.254.44.0/23'])

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

    def test_mutable_service_tag_is_rejected(self):
        self.config['images']['mysql'] = 'mysql:8.4'
        self.write()
        with self.assertRaisesRegex(ValueError, 'repository@sha256 digest: mysql'):
            load_config(self.path)

    def test_test_action_dispatches_a_replay_scoped_django_test(self):
        with patch('sys.argv', [
            'run.py', '--config', str(self.path), 'test', 'cms', 'targeted-cms-test',
            'contentstore.views.tests.test_course_index.TestCourseReIndex.test_example',
        ]), patch('run.ownership') as ownership, patch('run.docker_exec', return_value=['docker', 'exec']) as docker_exec, \
                patch('run.capture') as capture:
            replay_run.main()

        ownership.assert_called_once_with(self.config)
        docker_exec.assert_called_once_with(
            self.config,
            '/runtime/venv/bin/python',
            '/startup/run_py313_legacy_tests.py',
            'cms',
            'test',
            'contentstore.views.tests.test_course_index.TestCourseReIndex.test_example',
            settings='startup_cms',
        )
        capture.assert_called_once_with(self.config, 'targeted-cms-test', ['docker', 'exec'])

    def test_service_image_must_match_reviewed_digest_lock(self):
        self.config['images']['mysql'] = 'mysql@sha256:' + '0' * 64
        self.write()
        with self.assertRaisesRegex(ValueError, 'differs from reviewed digest lock: mysql'):
            load_config(self.path)

    def test_image_lock_requires_all_services_and_valid_manifest_digests(self):
        lock = read_json(IMAGE_LOCK_PATH)
        self.assertEqual(set(validate_image_lock(lock)['services']), set(SERVICES))
        lock['services'].pop('mysql')
        with self.assertRaisesRegex(ValueError, 'does not cover every service'):
            validate_image_lock(lock)
        lock = read_json(IMAGE_LOCK_PATH)
        lock['services']['mysql']['platform_manifests']['linux/amd64'] = 'sha256:bad'
        with self.assertRaisesRegex(ValueError, 'invalid platform digest: mysql'):
            validate_image_lock(lock)
        lock = read_json(IMAGE_LOCK_PATH)
        lock['schema_version'] = True
        with self.assertRaisesRegex(ValueError, 'schema version'):
            validate_image_lock(lock)
        lock = read_json(IMAGE_LOCK_PATH)
        lock['services']['mysql']['platform_manifests'][1] = 'sha256:' + 'a' * 64
        with self.assertRaisesRegex(ValueError, 'invalid platform: mysql'):
            validate_image_lock(lock)

    def test_repository_digest_normalizes_docker_hub_library_alias(self):
        digest = 'sha256:' + 'b' * 64
        self.assertEqual(image_reference_parts('mysql@' + digest),
                         image_reference_parts('docker.io/library/mysql@' + digest))
        self.assertNotEqual(image_reference_parts('mysql@' + digest),
                            image_reference_parts('registry.example/mysql@' + digest))

    def test_selected_service_image_records_locked_digest_and_platform(self):
        expected = self.config['images']['mysql']
        config_hash_value = config_hash(self.config)
        selected = validate_selected_image(
            self.config,
            'mysql',
            {'name': '/' + self.config['services']['mysql']['container'],
             'configured_image': 'docker.io/library/' + expected, 'image_id': 'sha256:' + 'b' * 64,
             'labels': {'py313.replay.config': config_hash_value}},
            {'Id': 'sha256:' + 'b' * 64,
             'RepoDigests': ['docker.io/library/' + expected], 'Os': 'linux',
             'Architecture': 'arm64', 'Variant': 'v8'},
        )
        self.assertEqual(selected['configured_image'], expected)
        self.assertEqual(selected['container_configured_image'], 'docker.io/library/' + expected)
        self.assertEqual(selected['image_id'], 'sha256:' + 'b' * 64)
        self.assertEqual(selected['platform'], {'os': 'linux', 'architecture': 'arm64', 'variant': 'v8'})
        self.assertEqual(selected['source_tag'], 'mysql:8.4')
        self.assertEqual(selected['locked_platform_manifest_digest'],
                         'sha256:b265fd63b9c8168801c1628b0b21e915846e81192f5a493682a1184cbd70d896')

    def test_selected_service_image_rejects_wrong_repository_digest(self):
        expected = self.config['images']['mysql']
        with self.assertRaisesRegex(ValueError, 'does not carry its locked repository digest: mysql'):
            validate_selected_image(
                self.config,
                'mysql',
                {'name': '/' + self.config['services']['mysql']['container'],
                 'configured_image': expected, 'image_id': 'sha256:' + 'b' * 64,
                 'labels': {'py313.replay.config': config_hash(self.config)}},
                {'Id': 'sha256:' + 'b' * 64, 'RepoDigests': ['mysql@sha256:' + 'c' * 64],
                 'Os': 'linux', 'Architecture': 'amd64'},
            )

    def test_selected_service_rejects_unlisted_platform_and_wrong_container(self):
        expected = self.config['images']['mysql']
        image_id = 'sha256:' + 'b' * 64
        container = {
            'name': '/' + self.config['services']['mysql']['container'],
            'configured_image': expected, 'image_id': image_id,
            'labels': {'py313.replay.config': config_hash(self.config)},
        }
        image = {'Id': image_id, 'RepoDigests': [expected], 'Os': 'linux',
                 'Architecture': 'riscv64', 'Variant': ''}
        with self.assertRaisesRegex(ValueError, 'platform is not present'):
            validate_selected_image(self.config, 'mysql', container, image)
        container['name'] = '/unexpected-container'
        with self.assertRaisesRegex(ValueError, 'container name differs'):
            validate_selected_image(self.config, 'mysql', container, image)

    def test_valkey_arm64_platform_without_variant_matches_index_descriptor(self):
        expected = self.config['images']['valkey']
        image_id = 'sha256:' + 'b' * 64
        selected = validate_selected_image(
            self.config,
            'valkey',
            {'name': '/' + self.config['services']['valkey']['container'],
             'configured_image': expected, 'image_id': image_id,
             'labels': {'py313.replay.config': config_hash(self.config)}},
            {'Id': image_id, 'RepoDigests': [expected], 'Os': 'linux',
             'Architecture': 'arm64', 'Variant': None},
        )
        self.assertEqual(selected['locked_platform_manifest_digest'],
                         'sha256:d2a1f2cbd6f69b933b82a930a44b7330b046bbd4c0d24bfc262967624c696dde')

    def test_runtime_selected_image_uses_exact_local_image_id(self):
        image_id = self.config['images']['runtime']
        selected = validate_selected_image(
            self.config, 'runtime',
            {'name': '/' + self.config['runtime_container'], 'configured_image': image_id,
             'image_id': image_id, 'labels': {'py313.replay.config': config_hash(self.config)}},
            {'Id': image_id, 'RepoDigests': [], 'Os': 'linux', 'Architecture': 'arm64', 'Variant': 'v8'},
        )
        self.assertEqual(selected['image_id'], image_id)
        self.assertIsNone(selected['index_digest'])

    def test_audit_inspects_configured_container_and_selected_image_id(self):
        expected = self.config['images']['mysql']
        image_id = 'sha256:' + 'b' * 64
        inspected_container = {
            'name': '/' + self.config['services']['mysql']['container'],
            'configured_image': expected, 'image_id': image_id,
            'labels': {'py313.replay.config': config_hash(self.config)},
        }
        inspected_image = {
            'Id': image_id, 'RepoDigests': [expected], 'Os': 'linux',
            'Architecture': 'amd64', 'Variant': '',
        }
        with patch.object(audit_and_collect.subprocess, 'check_output',
                          side_effect=[json.dumps(inspected_container), json.dumps(inspected_image)]) as inspect:
            selected = audit_and_collect.selected_image(self.config, 'mysql')

        self.assertEqual(selected['image_id'], image_id)
        calls = [mock_call.args[0] for mock_call in inspect.call_args_list]
        self.assertEqual(calls[0][-1], self.config['services']['mysql']['container'])
        self.assertEqual(calls[1][-1], image_id)

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
        self.assertEqual(env['PY313_REPLAY_ID'], self.config['run_id'])

    def test_run_scoped_acceptance_identities_are_private_and_not_overwritten(self):
        identity_dir = self.root / 'identities'
        identity_dir.mkdir(mode=0o700)
        identity_dir.chmod(0o700)
        target = identity_dir / 'acceptance.json'
        self.config.update(run_id='run53', credentials_file=str(target))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            provision(self.config)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        credentials = json.loads(target.read_text())
        self.assertEqual(credentials['run_id'], 'run53')
        self.assertEqual(set(credentials), {'run_id', 'staff', 'learner', 'learner2', 'other_org'})
        self.assertEqual({credentials[role]['username'] for role in ('staff', 'learner', 'learner2', 'other_org')},
                         {f'py313_run53_{role}' for role in ('staff', 'learner', 'learner2', 'other_org')})
        self.assertNotIn(credentials['staff']['password'], output.getvalue())
        original = target.read_bytes()
        with self.assertRaisesRegex(SystemExit, 'Refusing to overwrite'):
            provision(self.config)
        self.assertEqual(target.read_bytes(), original)

    def test_run_scoped_identity_provisioning_rejects_unsafe_run_id_and_shared_directory(self):
        identity_dir = self.root / 'identities'
        identity_dir.mkdir(mode=0o700)
        identity_dir.chmod(0o700)
        self.config['credentials_file'] = str(identity_dir / 'acceptance.json')
        self.config['run_id'] = '../outside'
        with self.assertRaisesRegex(SystemExit, 'run_id must be'):
            provision(self.config)
        self.config['run_id'] = 'run53'
        identity_dir.chmod(0o755)
        with self.assertRaisesRegex(SystemExit, 'mode 700'):
            provision(self.config)

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
