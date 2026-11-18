"""Resource collision and output reservation tests; no Docker daemon mutations."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

import run as replay_run
import audit_and_collect
from provision_acceptance import provision
from core import (APP_ROOT, SECRET_KEYS, SERVICES, capture, check_conflicts, check_platform_layout, environment, load_config,
                  physical_names, secret_values, source_repository_roots,
                  validate_path_isolation, validate_selected_image, config_hash, read_json,
                  IMAGE_LOCK_PATH, image_reference_parts, validate_image_lock, validate_network_subnet,
                  discovery_enabled, discovery_environment, discovery_lms_domain, discovery_names,
                  discovery_oidc_credentials, discovery_test_database)
import discovery


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

    def test_platform_mount_is_optional_and_never_changes_the_process_root(self):
        self.assertEqual(environment(self.config)['BRINGUP_PLATFORM_ROOT'], '/edx/app/edxapp/edx-platform')
        self.config['platform_mount'] = 'live'
        self.write()
        self.assertEqual(load_config(self.path)['platform_mount'], 'live')
        self.assertEqual(environment(self.config)['BRINGUP_PLATFORM_ROOT'], '/edx/app/edxapp/edx-platform')

    def test_runtime_receives_the_application_root(self):
        env = environment(self.config)
        self.assertEqual(env['BRINGUP_APP_ROOT'], '/edx/app/edxapp')
        self.assertEqual(env['BRINGUP_XMODULE_BUILD_ROOT'], '/edx/app/edxapp/py313/xmodule-source-build-v1')

    def test_platform_without_the_layout_contract_is_refused(self):
        platform = Path(self.config['platform_repo'])
        with self.assertRaisesRegex(ValueError, 'no ci/py313/layout.py'):
            check_platform_layout(platform)
        (platform / 'ci/py313').mkdir(parents=True)
        (platform / 'ci/py313/layout.py').write_text("DEFAULT_APP_ROOT = '/opt/other'\n")
        with self.assertRaisesRegex(ValueError, 'differs from the replay application root'):
            check_platform_layout(platform)
        (platform / 'ci/py313/layout.py').write_text("DEFAULT_APP_ROOT = '%s'\n" % APP_ROOT)
        check_platform_layout(platform)

    def test_theme_repo_is_optional_and_must_be_absolute_and_separate(self):
        self.assertNotIn('theme_repo', self.config)
        theme = self.root / 'theme'
        self.config['theme_repo'] = str(theme)
        self.write()
        self.assertEqual(load_config(self.path)['theme_repo'], str(theme))
        for value, message in (('theme', 'absolute'), (self.config['platform_repo'] + '/themes', 'separate'),
                               (str(Path(self.config['devstack_repo']).parent), 'separate')):
            with self.subTest(value=value):
                self.config['theme_repo'] = value
                self.write()
                with self.assertRaisesRegex(ValueError, message):
                    load_config(self.path)

    def test_replay_outputs_must_stay_outside_the_theme_repo(self):
        self.config['theme_repo'] = str(Path(self.config['export_dir']).parent)
        self.write()
        with self.assertRaises(ValueError):
            load_config(self.path)

    def test_unknown_platform_mount_is_rejected(self):
        self.config['platform_mount'] = 'volume'
        self.write()
        with self.assertRaisesRegex(ValueError, 'platform_mount'):
            load_config(self.path)

    def test_discovery_is_optional_and_absent_keys_keep_the_hash_stable(self):
        """A run without discovery must keep its config hash, or its existing resources stop matching."""
        before = config_hash(load_config(self.path))
        self.assertFalse(discovery_enabled(self.config))
        self.assertEqual(discovery.destroy_plan(self.config), ([], []))
        self.assertEqual(config_hash(load_config(self.path)), before)

    def test_discovery_derives_its_resources_from_run_id(self):
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        names = discovery_names(loaded)
        self.assertEqual(names['container'], 'run44' + '-discovery')
        self.assertEqual(names['volume'], 'run44' + '-discovery-data')
        self.assertEqual(names['database'], 'discovery_run44')
        self.assertEqual(loaded['discovery_port'], 18381)
        self.assertEqual(discovery.destroy_plan(loaded),
                         (['run44-discovery'], ['run44-discovery-data']))

    def test_discovery_reuses_the_run_services(self):
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        env = discovery_environment(load_config(self.path))
        # One database inside this run's MySQL, not a second server.
        self.assertEqual(env['DB_HOST'], self.config['services']['mysql']['container'])
        self.assertEqual(env['CACHE_LOCATION'], self.config['services']['memcached']['container'] + ':11211')
        self.assertEqual(env['DB_USER'], 'edxapp')

    def test_discovery_oidc_credentials_are_derived_per_run_and_agree_on_both_sides(self):
        """Discovery and the LMS seed must compute the same DOT credentials, and not a static pair."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        credentials = discovery_oidc_credentials(loaded)
        self.assertEqual(credentials, discovery_oidc_credentials(loaded))
        self.assertNotEqual(credentials['DISCOVERY_OIDC_KEY'], credentials['DISCOVERY_OIDC_SECRET'])
        # The LMS shell sees the same values, or the DOT Application would not match.
        env = environment(loaded)
        self.assertEqual(env['DISCOVERY_OIDC_KEY'], credentials['DISCOVERY_OIDC_KEY'])
        self.assertEqual(env['DISCOVERY_OIDC_SECRET'], credentials['DISCOVERY_OIDC_SECRET'])
        # Discovery's own container gets them too.
        self.assertEqual(discovery_environment(loaded)['DISCOVERY_OIDC_KEY'], credentials['DISCOVERY_OIDC_KEY'])
        # A different run secret yields a different pair.
        Path(self.config['secret_env']).write_text(
            ''.join(key + '=' + '2' * 48 + '\n' for key in SECRET_KEYS))
        self.assertNotEqual(discovery_oidc_credentials(load_config(self.path))['DISCOVERY_OIDC_KEY'],
                            credentials['DISCOVERY_OIDC_KEY'])

    def test_discovery_seeds_the_in_network_lms_address_not_the_loopback_port(self):
        """`refresh_course_metadata` prefixes `site.domain`, and discovery is a separate container."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        domain = discovery_lms_domain(loaded)
        self.assertEqual(domain, self.config['runtime_container'] + ':18000')
        self.assertNotIn(str(self.config['lms_port']), domain)
        env = discovery_environment(loaded)
        self.assertEqual(env['DISCOVERY_LMS_URL'], 'http://' + domain)
        self.assertEqual(env['DISCOVERY_STUDIO_URL'], 'http://' + self.config['runtime_container'] + ':18010')

    def test_discovery_schema_seeds_and_migrate_reseeds_without_duplicate_evidence(self):
        """`migrate` stays repeatable, so only `schema` may reserve a one-shot evidence file."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        recorded = []

        def record(config, label, command, **kwargs):
            recorded.append((label, command))

        with patch.object(discovery, 'define'), patch.object(discovery, 'provision_database'), \
                patch.object(discovery, 'ownership'), patch.object(discovery, 'capture', record), \
                patch.object(discovery.subprocess, 'run', return_value=type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()):
            discovery.schema(loaded)
            labels = [label for label, _ in recorded]
            self.assertIn('schema-discovery', labels)
            self.assertIn('seed-discovery-site-partner', labels)
            self.assertLess(labels.index('schema-discovery'), labels.index('seed-discovery-site-partner'))
            self.assertEqual(discovery.DISCOVERY_SEED_SCRIPT, 'ci/py313/seed_sites_and_partners.py')

            recorded.clear()
            discovery.migrate(loaded)
            # No evidence label is reused on a repeatable path.
            self.assertNotIn('schema-discovery', [label for label, _ in recorded])

    def test_discovery_schema_and_migrate_both_run_djangos_system_check(self):
        """`migrate` succeeding does not prove the configuration is sound, so `check` must run."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        captured = []
        executed = []

        def record(config, label, command, **kwargs):
            captured.append((label, ' '.join(str(part) for part in command)))

        def record_run(command, **kwargs):
            executed.append(' '.join(str(part) for part in command))
            return type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()

        with patch.object(discovery, 'define'), patch.object(discovery, 'provision_database'), \
                patch.object(discovery, 'ownership'), patch.object(discovery, 'capture', record), \
                patch.object(discovery.subprocess, 'run', side_effect=record_run):
            discovery.schema(loaded)
            commands = [text for label, text in captured if label == 'check-discovery']
            self.assertEqual(len(commands), 1)
            self.assertIn('manage.py check', commands[0])
            self.assertNotIn('--deploy', commands[0])
            # Ordered after the seed: a migrated-and-seeded database is what gets checked.
            labels = [label for label, _ in captured]
            self.assertLess(labels.index('seed-discovery-site-partner'), labels.index('check-discovery'))

            captured.clear()
            executed.clear()
            discovery.migrate(loaded)
            # The repeatable path runs the check without reserving an evidence file.
            self.assertNotIn('check-discovery', [label for label, _ in captured])
            self.assertTrue(any('manage.py check' in text for text in executed))

    def test_discovery_check_failure_stops_the_stage(self):
        """A failed `manage.py check` must abort, never be reported as a pass."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)

        def fail_if_check(command, **kwargs):
            result = type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
            if 'check' in command:
                result.returncode = 1
                result.stderr = 'SystemCheckError: something is wrong'
            return result

        with patch.object(discovery, 'define'), patch.object(discovery, 'ownership'), \
                patch.object(discovery, 'capture'), \
                patch.object(discovery.subprocess, 'run', side_effect=fail_if_check):
            with self.assertRaises(ValueError):
                discovery.check(loaded)

    def test_discovery_test_names_a_granted_database_instead_of_test_prefix(self):
        """Django would create `test_<name>`, a name edxapp holds no privilege on."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        database = discovery_test_database(loaded)
        self.assertEqual(database, loaded['discovery_database'] + '_test')
        # Never the bare application database: the suite must not touch run data.
        self.assertNotEqual(database, loaded['discovery_database'])
        captured = []

        def record(config, label, command, **kwargs):
            captured.append(' '.join(str(part) for part in command))

        with patch.object(discovery, 'define'), patch.object(discovery, 'ownership'), \
                patch.object(discovery, 'capture', record):
            discovery.test(loaded)
        self.assertEqual(len(captured), 1)
        command = captured[0]
        # The granted name is passed on both sides: the database and Django's TEST override.
        self.assertIn('DB_NAME=' + database, command)
        self.assertIn('DB_TEST_NAME=' + database, command)
        self.assertIn('django.db.backends.mysql', command)
        self.assertIn('--ds=course_discovery.settings.test', command)
        # Python comes from the isolated venv, never the image's global site-packages.
        self.assertIn(discovery.DISCOVERY_PYTHON, command)

    def test_discovery_test_passes_selectors_through(self):
        """`SELECTORS=` on the make target must reach pytest unchanged."""
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        loaded = load_config(self.path)
        captured = []

        def record(config, label, command, **kwargs):
            captured.append(list(command))

        with patch.object(discovery, 'define'), patch.object(discovery, 'ownership'), \
                patch.object(discovery, 'capture', record):
            discovery.test(loaded, ['course_discovery/apps/core', '-k', 'partner'])
        tail = captured[0][-3:]
        self.assertEqual(tail, ['course_discovery/apps/core', '-k', 'partner'])

    def test_discovery_image_is_required_and_validated(self):
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.write()
        with self.assertRaisesRegex(ValueError, 'discovery_image'):
            load_config(self.path)
        for value in ('', 'http://bad', 'has space'):
            with self.subTest(value=value):
                self.config['discovery_image'] = value
                self.write()
                with self.assertRaisesRegex(ValueError, 'discovery_image'):
                    load_config(self.path)

    def test_discovery_port_must_be_unique_and_in_range(self):
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        for value, message in ((self.config['lms_port'], 'differ'), (80, 'Invalid port'),
                               ('18381', 'Invalid port')):
            with self.subTest(value=value):
                self.config['discovery_port'] = value
                self.write()
                with self.assertRaisesRegex(ValueError, message):
                    load_config(self.path)

    def test_discovery_database_must_not_collide_with_the_platform(self):
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        for value, message in ((self.config['database'], 'differ'), ('Bad-Name', 'Invalid database'),
                               ('Ab', 'Invalid database')):
            with self.subTest(value=value):
                self.config['discovery_database'] = value
                self.write()
                with self.assertRaisesRegex(ValueError, message):
                    load_config(self.path)

    def test_discovery_repo_counts_as_a_source_for_path_isolation(self):
        self.config['discovery_repo'] = str(Path(self.config['export_dir']).parent)
        self.config['discovery_image'] = 'ltdps/discovery:py313-local'
        self.write()
        with self.assertRaisesRegex(ValueError, 'discovery_repo'):
            load_config(self.path)

    def test_generated_search_service_uses_bounded_heap(self):
        document = replay_run.compose(self.config)
        search = document['services']['elasticsearch']
        self.assertEqual(search['environment']['ES_JAVA_OPTS'], '-Xms256m -Xmx256m')
        self.assertEqual(search['mem_limit'], '2g')
        self.assertEqual(search['memswap_limit'], '3g')

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
            '/edx/app/edxapp/venvs/edxapp/bin/python',
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
            stream.write('BRINGUP_DATABASE_NAME=old-database\n')
        with self.assertRaisesRegex(ValueError, 'namespaces belong in config'):
            secret_values(self.config)

    def test_prior_environment_is_not_a_target_fallback(self):
        with patch.dict(os.environ, {'BRINGUP_RUNTIME_CONTAINER': 'old-container', 'BRINGUP_DATABASE_NAME': 'old-database'}):
            env = environment(self.config)
        self.assertEqual(env['BRINGUP_RUNTIME_CONTAINER'], self.config['runtime_container'])
        self.assertEqual(env['BRINGUP_DATABASE_NAME'], self.config['database'])
        self.assertEqual(env['BRINGUP_ACCEPTANCE_COURSE_ID'], self.config['course_key'])
        self.assertEqual(env['BRINGUP_REPLAY_ID'], self.config['run_id'])

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
                   'print(os.environ["BRINGUP_MYSQL_PASSWORD"])']
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

    def test_install_captures_installed_identity_after_install(self):
        with patch.object(replay_run, 'ownership') as ownership, \
             patch.object(replay_run, 'verify_prepared_export') as verify_export, \
             patch.object(replay_run, 'capture') as capture, \
             patch.object(replay_run, 'docker_exec', return_value=['docker', 'exec', 'identity']) as docker_exec:
            replay_run.install(self.config)
        self.assertEqual([call.args[1] for call in capture.call_args_list], [
            'prepare-install-inputs', 'install', 'platform-identity',
            'installed-companion-report', 'platform-identity-report',
            'install-receipt', 'resolved-lock', 'complete-lock'])
        docker_exec.assert_has_calls([
            unittest.mock.call(self.config, '/edx/app/edxapp/venvs/edxapp/bin/python', '-B', '/canary/verify-platform-identity.py'),
            unittest.mock.call(self.config, 'cat', '/edx/app/edxapp/py313/installed-companion-identity.json')])
        self.assertEqual(capture.call_args_list[-1].kwargs, {'show_output': False})
        ownership.assert_called_once_with(self.config)
        self.assertEqual(verify_export.call_args_list, [unittest.mock.call(self.config)] * 2)


class LayoutContractTests(unittest.TestCase):
    PROBE = Path(__file__).resolve().parents[1]
    RETIRED = re.compile(r'(?<![\w.<@/-])/runtime(?![\w.-])')

    def sources(self):
        for path in sorted(self.PROBE.rglob('*')):
            parts = path.relative_to(self.PROBE).parts
            if (path.suffix in ('.py', '.sh') and path.is_file()
                    and parts[0] not in ('dependencies', 'fixtures') and '__pycache__' not in parts):
                yield path

    def test_no_code_names_the_retired_runtime_root(self):
        # The two unit tests below assert that the retired mount is absent, so they must name it.
        # lifecycle.py probes it only to start a run created before the layout move: that run's
        # venv really is there, and probing it is what keeps such a run startable.
        allowed = {'replay/test_core.py', 'replay/test_run_export_identity.py', 'replay/lifecycle.py'}
        offenders = [str(path.relative_to(self.PROBE)) for path in self.sources()
                     if str(path.relative_to(self.PROBE)) not in allowed and self.RETIRED.search(path.read_text())]
        self.assertEqual(offenders, [])

    def test_every_repeated_default_equals_the_replay_root(self):
        found = 0
        for path in self.sources():
            for default in re.findall(r"BRINGUP_APP_ROOT['\"],\s*['\"]([^'\"]+)['\"]", path.read_text()):
                found += 1
                self.assertEqual(default, APP_ROOT, str(path.relative_to(self.PROBE)))
        self.assertGreater(found, 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
