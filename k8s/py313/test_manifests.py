"""Static checks of the k8s/py313 kustomizations. Needs `kubectl` (bundled kustomize) and no cluster.

    uv run --no-project --python 3.13 python -B -m unittest discover -s k8s/py313 -p 'test_manifests.py' -v

Rendering is `kubectl kustomize <dir>`. The YAML stream becomes JSON through `kubectl label --local -o json x-probe-`, a no-op
that needs no API server (create/apply --dry-run=client need discovery even with --validate=false), run against an empty
kubeconfig so that nothing can reach a real cluster.
"""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import generate_workers

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
STAGING_ENV = Path(os.environ.get(
    'STAGING_ENV', REPO.parent / 'triboo-doc/docs/staging/py313-staging-deploy-v2/staging.env'))

SECRET_ALLOW_LIST = {'edxapp-config', 'backing-credentials', 'local-prod-tls'}
LOCAL_NAMESPACE = 'py313-prod-local'
PLACEHOLDER_IMAGE = 'edxapp'
# Elasticsearch writes config/elasticsearch.keystore when ELASTIC_PASSWORD is set; no other container may write its root.
WRITABLE_ROOT_ALLOWED = {('elasticsearch', 'elasticsearch')}
# The Job reads this ConfigMap from the overlay; only the overlay-less `jobs` render may reference it without defining it.
OVERLAY_PROVIDED_CONFIGMAPS = {'py313-bringup-env'}
# Created at run time by scripts/gen-local-tls (it embeds the generated local CA), referenced only by the Traefik overlays.
RUNTIME_CONFIGMAPS = {'local-ca-bundle'}
SENSITIVE_NAME_PARTS = ('PASSWORD', 'SECRET', 'TOKEN', 'PRIVATE_KEY', 'API_KEY')

# staging.env WORKER_SET of PLATFORM_COMMIT b0db03a9e3e (py313-staging-deploy-v2): program -> system:queue:pool:concurrency.
EXPECTED_WORKERS = {
    'lms_default_1': ('lms', 'edx.lms.core.default', 'prefork', '1'),
    'lms_high_1': ('lms', 'edx.lms.core.high', 'solo', '1'),
    'lms_grade': ('lms', 'edx.lms.core.grade', 'prefork', '1'),
    'lms_progress': ('lms', 'edx.lms.core.progress', 'prefork', '1'),
    'cms_default_1': ('cms', 'edx.cms.core.default', 'prefork', '1'),
    'lms_high_mem_1': ('lms', 'edx.lms.core.high_mem', 'prefork', '1'),
    'lms_low_1': ('lms', 'edx.lms.core.low', 'prefork', '1'),
    'cms_low_1': ('cms', 'edx.cms.core.low', 'prefork', '1'),
}
EXPECTED_CRON = {
    'course-email-reminder': '0 4 * * *',
    'send-ilt-daily-mail': '0 5 * * *',
    'metrics': '0 3 * * *',
}
LOCAL_RUNNING_WORKERS = {'worker-lms-default', 'worker-cms-default'}

_cache = {}


def kustomization_dirs():
    return sorted(path.parent for path in HERE.rglob('kustomization.yaml'))


def render(directory):
    directory = Path(directory)
    if directory not in _cache:
        manifest = subprocess.run(['kubectl', 'kustomize', str(directory)], capture_output=True, text=True, check=False)
        if manifest.returncode != 0:
            raise AssertionError('kubectl kustomize %s failed:\n%s' % (directory, manifest.stderr))
        with tempfile.TemporaryDirectory() as empty:
            kubeconfig = Path(empty) / 'config'
            kubeconfig.write_text('')
            converted = subprocess.run(
                ['kubectl', 'label', '--local', '-f', '-', '-o', 'json', 'x-probe-'],
                input=manifest.stdout, capture_output=True, text=True, check=False,
                env={**os.environ, 'KUBECONFIG': str(kubeconfig)})
        if converted.returncode != 0:
            raise AssertionError('JSON conversion of %s failed:\n%s' % (directory, converted.stderr))
        decoder, text, objects, position = json.JSONDecoder(), converted.stdout, [], 0
        while position < len(text):
            if text[position].isspace():
                position += 1
                continue
            item, position = decoder.raw_decode(text, position)
            objects.extend(item['items'] if item.get('kind') == 'List' else [item])
        _cache[directory] = objects
    return _cache[directory]


def pod_templates(objects):
    """(kind, name, pod template) for every workload."""
    for obj in objects:
        kind, name = obj['kind'], obj['metadata']['name']
        if kind in ('Deployment', 'StatefulSet', 'Job'):
            yield kind, name, obj['spec']['template']
        elif kind == 'CronJob':
            yield kind, name, obj['spec']['jobTemplate']['spec']['template']


def containers(template):
    spec = template['spec']
    for container in spec.get('initContainers', []):
        yield container
    for container in spec['containers']:
        yield container


def of_kind(objects, kind):
    return [obj for obj in objects if obj['kind'] == kind]


def named(objects, kind, name):
    found = [obj for obj in of_kind(objects, kind) if obj['metadata']['name'] == name]
    assert len(found) == 1, (kind, name, len(found))
    return found[0]


def worker_arguments(container):
    """(system, queue, pool, concurrency, hostname) from the entrypoint arguments of a worker container."""
    args = container['args']
    assert args[0] == 'worker' and args[1] in ('lms', 'cms'), args
    options = dict(a[2:].split('=', 1) for a in args[2:] if a.startswith('--') and '=' in a)
    solo = '--pool=solo' in args
    concurrency = '1' if solo else options['concurrency']
    return args[1], options['queues'], 'solo' if solo else 'prefork', concurrency, options['hostname']


class RenderTest(unittest.TestCase):
    def test_kubectl_is_available(self):
        self.assertIsNotNone(shutil.which('kubectl'), 'kubectl (with bundled kustomize) is required')

    def test_every_kustomization_renders(self):
        directories = kustomization_dirs()
        self.assertGreaterEqual(len(directories), 6)
        relative = {str(d.relative_to(HERE)) for d in directories}
        for expected in ('traefik', 'traefik/crds', 'overlays/orbstack-local-traefik', 'overlays/orbstack-local-traefik/ingress',
                         'overlays/orbstack-local-traefik/jobs'):
            self.assertIn(expected, relative)
        for directory in directories:
            with self.subTest(directory=str(directory.relative_to(HERE))):
                self.assertTrue(render(directory))


class WorkloadSecurityTest(unittest.TestCase):
    def check_pod(self, label, kind, name, template, overlay):
        spec = template['spec']
        pod_context = spec.get('securityContext', {})
        for flag in ('hostNetwork', 'hostPID', 'hostIPC'):
            self.assertFalse(spec.get(flag), '%s %s' % (label, flag))
        for volume in spec.get('volumes', []):
            self.assertNotIn('hostPath', volume, label)
        self.assertEqual(pod_context.get('seccompProfile', {}).get('type'), 'RuntimeDefault', label)
        for container in containers(template):
            where = '%s/%s' % (label, container['name'])
            context = container.get('securityContext', {})
            self.assertTrue(context.get('runAsNonRoot', pod_context.get('runAsNonRoot')), where)
            user = context.get('runAsUser', pod_context.get('runAsUser'))
            self.assertIsInstance(user, int, where + ' needs a numeric runAsUser')
            self.assertNotEqual(user, 0, where)
            self.assertIs(context.get('allowPrivilegeEscalation'), False, where)
            self.assertFalse(context.get('privileged'), where)
            self.assertIn('ALL', context.get('capabilities', {}).get('drop', []), where)
            for port in container.get('ports', []):
                self.assertNotIn('hostPort', port, where)
            read_only = context.get('readOnlyRootFilesystem')
            if (name, container['name']) in WRITABLE_ROOT_ALLOWED:
                self.assertIs(read_only, False, where + ' exception no longer needed? remove it from WRITABLE_ROOT_ALLOWED')
            else:
                self.assertIs(read_only, True, where)
            for section in ('requests', 'limits'):
                for resource in ('cpu', 'memory'):
                    self.assertTrue(container.get('resources', {}).get(section, {}).get(resource), '%s %s.%s' % (where, section, resource))
            image = container.get('image', '')
            self.assertTrue(image, where + ' has no image')
            if image.rsplit('/', 1)[-1] == PLACEHOLDER_IMAGE:
                self.assertFalse(overlay, where + ' still uses the placeholder image in an overlay')
            else:
                last = image.rsplit('/', 1)[-1]
                self.assertTrue('@sha256:' in last or ':' in last, where + ' has no tag: ' + image)
                self.assertFalse(last.endswith(':latest'), where)
            for var in container.get('env', []):
                if any(part in var['name'].upper() for part in SENSITIVE_NAME_PARTS):
                    self.assertIn('valueFrom', var, '%s %s must come from a Secret' % (where, var['name']))
                    self.assertNotIn('value', var, where)

    def test_pod_hardening_in_every_render(self):
        for directory in kustomization_dirs():
            objects = render(directory)
            overlay = 'overlays' in directory.parts
            label = str(directory.relative_to(HERE))
            for kind, name, template in pod_templates(objects):
                with self.subTest(directory=label, workload='%s/%s' % (kind, name)):
                    self.check_pod('%s:%s/%s' % (label, kind, name), kind, name, template, overlay)

    def test_secret_references_are_allow_listed_and_no_secret_object_is_rendered(self):
        for directory in kustomization_dirs():
            objects = render(directory)
            label = str(directory.relative_to(HERE))
            self.assertEqual(of_kind(objects, 'Secret'), [], label + ' renders a Secret')
            configmaps = {obj['metadata']['name'] for obj in of_kind(objects, 'ConfigMap')}
            for kind, name, template in pod_templates(objects):
                where = '%s:%s/%s' % (label, kind, name)
                for volume in template['spec'].get('volumes', []):
                    if 'secret' in volume:
                        self.assertIn(volume['secret']['secretName'], SECRET_ALLOW_LIST, where)
                    if 'configMap' in volume:
                        wanted = volume['configMap']['name']
                        if wanted in RUNTIME_CONFIGMAPS:
                            self.assertIn('traefik', label, where + ' only the Traefik mode mounts a run-time ConfigMap')
                            continue
                        self.assertIn(wanted, configmaps, where)
                for container in containers(template):
                    for var in container.get('env', []):
                        source = var.get('valueFrom', {})
                        if 'secretKeyRef' in source:
                            self.assertIn(source['secretKeyRef']['name'], SECRET_ALLOW_LIST, where)
                        if 'configMapKeyRef' in source:
                            self.assertIn(source['configMapKeyRef']['name'], configmaps, where)
                    for ref in container.get('envFrom', []):
                        self.assertNotIn('secretRef', ref, where + ' must name single keys, not a whole Secret')
                        wanted = ref['configMapRef']['name']
                        if wanted in OVERLAY_PROVIDED_CONFIGMAPS and 'overlays' not in directory.parts:
                            continue
                        self.assertIn(wanted, configmaps, where)

    def test_config_secret_mount_contract(self):
        for directory in (HERE / 'base', HERE / 'overlays/orbstack-local'):
            for kind, name, template in pod_templates(render(directory)):
                if name == 'db-init' or template['metadata']['labels']['app.kubernetes.io/name'] != 'edxapp':
                    continue
                with self.subTest(directory=str(directory.relative_to(HERE)), workload=name):
                    volumes = {v['name']: v for v in template['spec']['volumes']}
                    secret = volumes['config']['secret']
                    self.assertEqual(secret['secretName'], 'edxapp-config')
                    self.assertEqual(secret['defaultMode'], 0o440)
                    self.assertEqual(template['spec']['securityContext']['fsGroup'], 1000)
                    for container in template['spec']['containers']:
                        mounts = {m['mountPath']: m for m in container['volumeMounts']}
                        self.assertTrue(mounts['/edx/app/edxapp/py313-config']['readOnly'])
                        for path in ('/tmp', '/edx/var/log/lms', '/edx/var/log/cms', '/edx/var/edxapp/media', '/edx/var/edxapp/data'):
                            self.assertIn(path, mounts)
                        self.assertNotIn('/edx/var/edxapp', mounts, 'never mount over the static root')

    def test_service_account_has_no_token(self):
        objects = render(HERE / 'base')
        self.assertIs(named(objects, 'ServiceAccount', 'edxapp')['automountServiceAccountToken'], False)
        for kind, name, template in pod_templates(objects):
            self.assertIs(template['spec'].get('automountServiceAccountToken'), False, name)


class BaseContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects = render(HERE / 'base')

    def test_workers_match_staging_worker_set(self):
        deployments = [o for o in of_kind(self.objects, 'Deployment') if o['metadata']['name'].startswith('worker-')]
        found = {}
        for deployment in deployments:
            program = deployment['metadata']['annotations']['py313.learningtribes.com/staging-program']
            container = deployment['spec']['template']['spec']['containers'][0]
            system, queue, pool, concurrency, hostname = worker_arguments(container)
            self.assertEqual(hostname, queue + '.%h')
            self.assertIn('--heartbeat-interval=120', container['args'])
            self.assertIn('--loglevel=info', container['args'])
            self.assertEqual(deployment['spec']['replicas'], 1, program)
            found[program] = (system, queue, pool, concurrency)
        self.assertEqual(found, EXPECTED_WORKERS)

    @unittest.skipUnless(STAGING_ENV.is_file(), 'staging.env of triboo-doc is not next to this repository (set STAGING_ENV)')
    def test_workers_match_staging_env_file(self):
        values = {}
        for line in STAGING_ENV.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
        programs = values['WORKER_SET'].split(',')
        self.assertEqual(set(programs), set(EXPECTED_WORKERS))
        for program in programs:
            self.assertEqual(tuple(values['WORKER_' + program].split(':')), EXPECTED_WORKERS[program], program)
        for name, key in (('course-email-reminder', 'COURSE_EMAIL_REMINDER'), ('send-ilt-daily-mail', 'SEND_ILT_DAILY_MAIL'),
                          ('metrics', 'METRICS')):
            self.assertEqual(values['CRON_%s_SCHEDULE' % key].strip("'"), EXPECTED_CRON[name])

    def test_checked_in_workers_equal_generator_output(self):
        self.assertEqual((HERE / 'base/workers.yaml').read_text(), generate_workers.render())

    def test_worker_grace_period_is_present_and_overridable(self):
        for deployment in of_kind(self.objects, 'Deployment'):
            if deployment['metadata']['labels']['app.kubernetes.io/component'] == 'worker':
                self.assertEqual(deployment['spec']['template']['spec']['terminationGracePeriodSeconds'], 3600)

    def test_web_probes(self):
        for name, port in (('lms', 8000), ('cms', 8010)):
            with self.subTest(name=name):
                deployment = named(self.objects, 'Deployment', name)
                container = deployment['spec']['template']['spec']['containers'][0]
                self.assertEqual(container['args'], [name])
                self.assertEqual(container['ports'][0]['containerPort'], port)
                self.assertIn('startupProbe', container)
                startup = container['startupProbe']
                self.assertGreaterEqual(startup['failureThreshold'] * startup['periodSeconds'], 600)
                readiness = container['readinessProbe']['httpGet']
                self.assertEqual(readiness['path'], '/heartbeat')
                self.assertEqual(readiness['port'], 'http')
                self.assertTrue([h for h in readiness['httpHeaders'] if h['name'] == 'Host' and h['value']])
                self.assertIn('tcpSocket', container['livenessProbe'])
                env = {e['name']: e.get('value') for e in container['env']}
                self.assertEqual(env['PORT'], str(port))
                self.assertEqual(env['CONFIG_ROOT'], '/edx/app/edxapp/py313-config')
                for var in ('GUNICORN_WORKERS', 'GUNICORN_TIMEOUT', 'GUNICORN_MAX_REQUESTS', 'EDXAPP_SETTINGS'):
                    self.assertIn(var, env)

    def test_services_select_pods_and_ports_exist(self):
        workloads = {}
        for kind, name, template in pod_templates(self.objects):
            workloads[name] = template
        for service in of_kind(self.objects, 'Service'):
            name = service['metadata']['name']
            self.assertEqual(service['spec']['type'], 'ClusterIP', name)
            selector = service['spec']['selector']
            matching = [t for t in workloads.values() if selector.items() <= t['metadata']['labels'].items()]
            self.assertEqual(len(matching), 1, name)
            ports = {p['name'] for c in matching[0]['spec']['containers'] for p in c.get('ports', [])}
            for port in service['spec']['ports']:
                self.assertIn(port['targetPort'], ports, name)

    def test_selectors_match_template_labels_and_pdbs_select_web(self):
        for obj in of_kind(self.objects, 'Deployment'):
            selector = obj['spec']['selector']['matchLabels']
            labels = obj['spec']['template']['metadata']['labels']
            self.assertTrue(selector.items() <= labels.items(), obj['metadata']['name'])
        pdbs = {p['metadata']['name']: p for p in of_kind(self.objects, 'PodDisruptionBudget')}
        self.assertEqual(set(pdbs), {'lms', 'cms'})
        for name, pdb in pdbs.items():
            deployment = named(self.objects, 'Deployment', name)
            self.assertEqual(pdb['spec']['selector']['matchLabels'], deployment['spec']['selector']['matchLabels'])

    def test_common_labels(self):
        for obj in self.objects:
            labels = obj['metadata']['labels']
            self.assertIn('app.kubernetes.io/name', labels, obj['metadata']['name'])
            self.assertEqual(labels['app.kubernetes.io/part-of'], 'openedx')
        for kind, name, template in pod_templates(self.objects):
            self.assertIn('app.kubernetes.io/name', template['metadata']['labels'], name)

    def test_no_ingress_and_no_secret(self):
        kinds = {obj['kind'] for obj in self.objects}
        self.assertNotIn('Ingress', kinds)
        self.assertNotIn('Secret', kinds)

    def test_cronjobs_match_staging_and_are_suspended(self):
        for directory in (HERE / 'base', HERE / 'overlays/orbstack-local'):
            crons = {o['metadata']['name']: o for o in of_kind(render(directory), 'CronJob')}
            self.assertEqual({name: c['spec']['schedule'] for name, c in crons.items()}, EXPECTED_CRON)
            for name, cron in crons.items():
                self.assertIs(cron['spec']['suspend'], True, name)
                self.assertEqual(cron['spec']['concurrencyPolicy'], 'Forbid', name)
                self.assertNotIn('timeZone', cron['spec'])
                args = cron['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['args']
                self.assertEqual(args[:2], ['manage', 'lms'], name)
                self.assertNotIn('sudo', ' '.join(args))


class JobsContractTest(unittest.TestCase):
    def test_db_init_runs_platform_scripts_in_order_and_never_wipes(self):
        job = named(render(HERE / 'jobs'), 'Job', 'db-init')
        container = job['spec']['template']['spec']['containers'][0]
        script = container['args'][2]
        order = [script.index(name) for name in (
            '/startup/initialize_schema.py', '/startup/seed_local_host_sites.py',
            '/startup/seed_completion_tracking.py', '/startup/seed_themes.py')]
        self.assertEqual(order, sorted(order))
        self.assertIn('startup_schema /startup/initialize_schema.py', script)
        for forbidden in ('drop', 'DROP', 'flush', 'wipe', 'drop_collection', 'reset_db', 'sqlflush'):
            self.assertNotIn(forbidden, script)
        self.assertNotIn('--settings', script)
        self.assertEqual(job['spec']['backoffLimit'], 0)
        for path in ('/tmp', '/edx/app/edxapp/py313/config', '/edx/var/log/lms', '/edx/var/log/cms'):
            self.assertIn(path, {m['mountPath'] for m in container['volumeMounts']})
        volumes = {v['name'] for v in job['spec']['template']['spec']['volumes']}
        self.assertLessEqual({m['name'] for m in container['volumeMounts']}, volumes)

    def test_db_init_environment_covers_the_startup_settings_contract(self):
        job = named(render(HERE / 'jobs'), 'Job', 'db-init')
        container = job['spec']['template']['spec']['containers'][0]
        names = {e['name'] for e in container['env']}
        # Variables read with os.environ[...] by settings/local_runtime.py that the ConfigMap does not carry.
        for required in ('BRINGUP_DATABASE_NAME', 'BRINGUP_MYSQL_PASSWORD', 'BRINGUP_MONGO_PASSWORD', 'BRINGUP_RABBITMQ_PASSWORD',
                         'BRINGUP_STARTUP_SECRET_KEY', 'BRINGUP_STARTUP_XQUEUE_PASSWORD'):
            self.assertIn(required, names)

    def test_local_bringup_env_has_every_variable_the_job_needs_from_the_config_map(self):
        configmap = named(render(HERE / 'overlays/orbstack-local/jobs'), 'ConfigMap', 'py313-bringup-env')
        for required in ('BRINGUP_LMS_DOMAIN', 'BRINGUP_CMS_DOMAIN', 'BRINGUP_MONGO_DB', 'BRINGUP_CACHE_PREFIX',
                         'BRINGUP_ES_INDEX_PREFIX', 'BRINGUP_MYSQL_HOST', 'BRINGUP_MONGO_HOST', 'BRINGUP_MEMCACHED_HOST',
                         'BRINGUP_RABBITMQ_HOST', 'BRINGUP_ES_HOST'):
            self.assertTrue(configmap['data'].get(required), required)
        self.assertNotIn('', {v for v in configmap['data'].values()})
        for key in configmap['data']:
            self.assertFalse(any(part in key.upper() for part in SENSITIVE_NAME_PARTS), key)


class OrbstackOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects = render(HERE / 'overlays/orbstack-local')
        cls.all_workers = render(HERE / 'overlays/orbstack-local-all-workers')

    def test_namespace(self):
        namespaces = of_kind(self.objects, 'Namespace')
        self.assertEqual([n['metadata']['name'] for n in namespaces], [LOCAL_NAMESPACE])
        for obj in self.objects:
            if obj['kind'] != 'Namespace':
                self.assertEqual(obj['metadata'].get('namespace'), LOCAL_NAMESPACE, '%s/%s' % (obj['kind'], obj['metadata']['name']))
        for obj in render(HERE / 'overlays/orbstack-local/jobs'):
            self.assertEqual(obj['metadata'].get('namespace'), LOCAL_NAMESPACE)

    def test_image_override_and_pull_policy(self):
        for objects in (self.objects, render(HERE / 'overlays/orbstack-local/jobs')):
            for kind, name, template in pod_templates(objects):
                container = template['spec']['containers'][0]
                if name in ('mysql', 'mongodb', 'elasticsearch', 'rabbitmq', 'memcached'):
                    continue
                self.assertEqual(container['image'], 'edxapp:py313-prodimage-b0db03a-local', name)
                self.assertEqual(container['imagePullPolicy'], 'IfNotPresent', name)

    def test_replicas_and_minimum_workers(self):
        self.assertEqual(named(self.objects, 'Deployment', 'lms')['spec']['replicas'], 1)
        self.assertEqual(named(self.objects, 'Deployment', 'cms')['spec']['replicas'], 1)
        running = {o['metadata']['name'] for o in of_kind(self.objects, 'Deployment')
                   if o['metadata']['name'].startswith('worker-') and o['spec']['replicas'] > 0}
        self.assertEqual(running, LOCAL_RUNNING_WORKERS)
        everything = {o['metadata']['name'] for o in of_kind(self.all_workers, 'Deployment')
                      if o['metadata']['name'].startswith('worker-') and o['spec']['replicas'] > 0}
        self.assertEqual(len(everything), len(EXPECTED_WORKERS))

    def test_worker_grace_override_is_applied(self):
        for deployment in of_kind(self.objects, 'Deployment'):
            if deployment['metadata']['name'].startswith('worker-'):
                self.assertEqual(deployment['spec']['template']['spec']['terminationGracePeriodSeconds'], 60)

    def test_backing_services(self):
        statefulsets = {o['metadata']['name']: o for o in of_kind(self.objects, 'StatefulSet')}
        self.assertEqual(set(statefulsets), {'mysql', 'mongodb', 'elasticsearch', 'rabbitmq'})
        images = {name: s['spec']['template']['spec']['containers'][0]['image'] for name, s in statefulsets.items()}
        self.assertEqual(images, {'mysql': 'mysql:8.4.13', 'mongodb': 'mongo:8.0', 'elasticsearch': 'elasticsearch:8.19.0',
                                  'rabbitmq': 'rabbitmq:4.3'})
        self.assertEqual(named(self.objects, 'Deployment', 'memcached')['spec']['template']['spec']['containers'][0]['image'],
                         'memcached:1.6.45')
        for name, statefulset in statefulsets.items():
            for claim in statefulset['spec']['volumeClaimTemplates']:
                self.assertEqual(claim['spec']['storageClassName'], 'local-path', name)
        self.assertEqual({s['metadata']['name'] for s in of_kind(self.objects, 'Service')},
                         {'lms', 'cms', 'mysql', 'mongodb', 'elasticsearch', 'rabbitmq', 'memcached'})

    def test_elasticsearch_is_secured_and_sized(self):
        container = named(self.objects, 'StatefulSet', 'elasticsearch')['spec']['template']['spec']['containers'][0]
        env = {e['name']: e.get('value') for e in container['env']}
        self.assertEqual(env['xpack.security.enabled'], 'true')
        self.assertEqual(env['xpack.security.http.ssl.enabled'], 'true')
        self.assertEqual(env['discovery.type'], 'single-node')
        self.assertEqual(env['ES_JAVA_OPTS'], '-Xms512m -Xmx512m')

    def test_elasticsearch_certutil_writes_only_below_the_scratch_directory(self):
        init = named(self.objects, 'StatefulSet', 'elasticsearch')['spec']['template']['spec']['initContainers'][0]
        script = init['command'][-1]
        # certutil resolves a relative --out against its read-only home directory, not the working directory.
        targets = re.findall(r'--out\s+(\S+)', script)
        self.assertEqual(len(targets), 2, targets)
        self.assertTrue(all(target.startswith('"$work/') for target in targets), targets)

    def test_rabbitmq_settings_equal_the_devstack_file(self):
        source = (REPO / 'docker/py313/rabbitmq/20-permit-transient-nonexcl.conf').read_text()
        configmap = named(self.objects, 'ConfigMap', 'rabbitmq-conf')
        self.assertEqual(configmap['data']['20-permit-transient-nonexcl.conf'], source)

    def test_no_ingress_and_no_valkey(self):
        kinds = {o['kind'] for o in self.objects}
        self.assertNotIn('Ingress', kinds)
        names = {o['metadata']['name'] for o in self.objects}
        self.assertNotIn('valkey', names)


BASE_DOMAIN = 'local-prod.7mud.com'
TRAEFIK_DIR = HERE / 'traefik'
TRAEFIK_OVERLAY = HERE / 'overlays/orbstack-local-traefik'
FEATURE_LABEL = ('py313.learningtribes.com/feature', 'traefik-local')
CA_BUNDLE = '/etc/local-ca/ca-bundle.crt'


def env_file(path):
    return dict(line.split('=', 1) for line in Path(path).read_text().splitlines() if '=' in line)


class TraefikControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects = render(TRAEFIK_DIR)
        cls.crds = render(TRAEFIK_DIR / 'crds')
        cls.deployment = named(cls.objects, 'Deployment', 'traefik')
        cls.container = cls.deployment['spec']['template']['spec']['containers'][0]

    def test_image_is_a_pinned_v3_release(self):
        self.assertRegex(self.container['image'], r'^traefik:v3\.\d+\.\d+$')
        crd_header = (TRAEFIK_DIR / 'crds/crds.yaml').read_text()
        self.assertIn('Traefik ' + self.container['image'].split(':')[1], crd_header, 'CRDs and image are from different Traefik versions')

    def test_entrypoints_redirect_and_tls(self):
        args = self.container['args']
        for arg in ('--entrypoints.web.address=:8000', '--entrypoints.websecure.address=:8443',
                    '--entrypoints.web.http.redirections.entryPoint.to=:443',
                    '--entrypoints.web.http.redirections.entryPoint.scheme=https',
                    '--entrypoints.websecure.http.tls=true', '--accesslog=true', '--ping=true'):
            self.assertIn(arg, args)
        ports = {p['name']: p['containerPort'] for p in self.container['ports']}
        self.assertEqual(ports, {'web': 8000, 'websecure': 8443, 'ping': 9000})

    def test_forwarded_headers_are_not_trusted_from_clients(self):
        joined = ' '.join(self.container['args'])
        self.assertIn('--global.aliasHeadersStrategy=delete', self.container['args'])
        self.assertNotIn('forwardedHeaders', joined, 'default (untrusted) handling must stay: Traefik then sets X-Forwarded-Proto itself')
        self.assertNotIn('--api.insecure', joined)
        self.assertNotIn('proxyProtocol', joined)

    def test_probes_use_ping_and_the_service_exposes_only_80_and_443(self):
        for probe in ('readinessProbe', 'livenessProbe'):
            self.assertEqual(self.container[probe]['httpGet'], {'path': '/ping', 'port': 'ping'})
        service = named(self.objects, 'Service', 'traefik')
        self.assertEqual(service['spec']['type'], 'LoadBalancer')
        self.assertEqual({(p['name'], p['port'], p['targetPort']) for p in service['spec']['ports']},
                         {('web', 80, 'web'), ('websecure', 443, 'websecure')})
        self.assertEqual(service['spec']['selector'].items() <= self.deployment['spec']['template']['metadata']['labels'].items(), True)

    def test_default_certificate_secret(self):
        store = named(self.objects, 'TLSStore', 'default')
        self.assertEqual(store['spec']['defaultCertificate']['secretName'], 'local-prod-tls')
        self.assertEqual(store['metadata']['namespace'], 'traefik')

    def test_cluster_level_objects_are_the_documented_set(self):
        cluster = {(o['kind'], o['metadata']['name']) for o in self.objects
                   if o['kind'] in ('Namespace', 'ClusterRole', 'ClusterRoleBinding', 'CustomResourceDefinition')}
        self.assertEqual(cluster, {('Namespace', 'traefik'), ('ClusterRole', 'traefik-py313-local'),
                                   ('ClusterRoleBinding', 'traefik-py313-local')})
        crds = {o['metadata']['name'] for o in self.crds}
        self.assertEqual(crds, {r + '.traefik.io' for r in (
            'ingressroutes', 'ingressroutetcps', 'ingressrouteudps', 'middlewares', 'middlewaretcps', 'serverstransports',
            'serverstransporttcps', 'tlsoptions', 'tlsstores', 'traefikservices')})
        for crd in self.crds:
            self.assertEqual(crd['spec']['group'], 'traefik.io', crd['metadata']['name'])
        for obj in self.objects + self.crds:
            self.assertEqual(obj['metadata']['labels'][FEATURE_LABEL[0]], FEATURE_LABEL[1], obj['metadata']['name'])
            self.assertTrue(obj['metadata'].get('namespace') in (None, 'traefik'), obj['metadata']['name'])
        namespace = named(self.objects, 'Namespace', 'traefik')
        self.assertEqual(namespace['metadata']['labels']['pod-security.kubernetes.io/enforce'], 'restricted')

    def test_rbac_covers_every_installed_crd_kind_read_only(self):
        rules = named(self.objects, 'ClusterRole', 'traefik-py313-local')['rules']
        granted = {r for rule in rules if rule['apiGroups'] == ['traefik.io'] for r in rule['resources']}
        self.assertEqual(granted, {crd['spec']['names']['plural'] for crd in self.crds},
                         'the CRD provider watches every kind: a missing permission or CRD stalls its configuration')

    def test_rbac_has_no_wildcards_and_no_write_except_ingress_status(self):
        rules = named(self.objects, 'ClusterRole', 'traefik-py313-local')['rules']
        for rule in rules:
            for field in ('apiGroups', 'resources', 'verbs'):
                self.assertNotIn('*', rule[field])
            if set(rule['verbs']) - {'get', 'list', 'watch'}:
                self.assertEqual((rule['resources'], rule['verbs']), (['ingresses/status'], ['update']))
        binding = named(self.objects, 'ClusterRoleBinding', 'traefik-py313-local')
        self.assertEqual(binding['subjects'], [{'kind': 'ServiceAccount', 'name': 'traefik', 'namespace': 'traefik'}])

    def test_buffering_spool_fits_the_tmp_volume(self):
        volume = {v['name']: v for v in self.deployment['spec']['template']['spec']['volumes']}['tmp']
        self.assertEqual(volume['emptyDir']['sizeLimit'], '3Gi')
        self.assertIn('/tmp', {m['mountPath'] for m in self.container['volumeMounts']})


class TraefikOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects = render(TRAEFIK_OVERLAY)
        cls.ingress_objects = render(TRAEFIK_OVERLAY / 'ingress')
        cls.jobs = render(TRAEFIK_OVERLAY / 'jobs')
        cls.base_objects = render(HERE / 'overlays/orbstack-local')
        cls.bringup = env_file(TRAEFIK_OVERLAY / 'jobs/bringup.env')

    def test_site_domains_scheme_and_cookie_domain(self):
        self.assertEqual(self.bringup['BRINGUP_LMS_DOMAIN'], 'lms.' + BASE_DOMAIN)
        self.assertEqual(self.bringup['BRINGUP_CMS_DOMAIN'], 'studio.' + BASE_DOMAIN)
        self.assertEqual(self.bringup['BRINGUP_SCHEME'], 'https')
        self.assertEqual(self.bringup['BRINGUP_LMS_ROOT_URL'], 'https://lms.' + BASE_DOMAIN)
        self.assertEqual(self.bringup['BRINGUP_CMS_ROOT_URL'], 'https://studio.' + BASE_DOMAIN)
        self.assertEqual(self.bringup['BRINGUP_SESSION_COOKIE_DOMAIN'], '.' + BASE_DOMAIN)
        config = named(self.jobs, 'ConfigMap', 'py313-bringup-env')['data']
        for key, value in self.bringup.items():
            self.assertEqual(config[key], value)
        # keys the Traefik file does not override still come from the local overlay
        for key, value in env_file(HERE / 'overlays/orbstack-local/jobs/bringup.env').items():
            if key not in self.bringup:
                self.assertEqual(config[key], value, key)
        self.assertEqual(env_file(HERE / 'overlays/orbstack-local/jobs/bringup.env')['BRINGUP_LMS_DOMAIN'], 'localhost:18000',
                         'the port-forward flow keeps its own domains')

    def test_every_ingress_host_is_in_the_base_domain_and_matches_the_site_domains(self):
        hosts = set()
        for ingress in of_kind(self.objects, 'Ingress'):
            for rule in ingress['spec']['rules']:
                hosts.add(rule['host'])
            for tls in ingress['spec']['tls']:
                self.assertEqual(tls['secretName'], 'local-prod-tls')
                for host in tls['hosts']:
                    self.assertTrue(host.endswith('.' + BASE_DOMAIN), host)
        self.assertEqual(hosts, {self.bringup['BRINGUP_LMS_DOMAIN'], self.bringup['BRINGUP_CMS_DOMAIN']})
        for host in hosts:
            self.assertTrue(host.endswith('.' + BASE_DOMAIN), host)

    def test_ingress_backends_exist_and_static_is_routed_for_both_hosts(self):
        services = {s['metadata']['name']: {p['name'] for p in s['spec']['ports']} for s in of_kind(self.objects, 'Service')}
        routes = {}
        for ingress in of_kind(self.objects, 'Ingress'):
            for rule in ingress['spec']['rules']:
                for path in rule['http']['paths']:
                    backend = path['backend']['service']
                    self.assertIn(backend['name'], services, ingress['metadata']['name'])
                    self.assertIn(backend['port']['name'], services[backend['name']], ingress['metadata']['name'])
                    routes[(rule['host'], path['path'])] = backend['name']
        self.assertEqual(routes, {
            ('lms.' + BASE_DOMAIN, '/'): 'lms', ('studio.' + BASE_DOMAIN, '/'): 'cms',
            ('lms.' + BASE_DOMAIN, '/static'): 'static', ('studio.' + BASE_DOMAIN, '/static'): 'static'})
        for ingress in of_kind(self.objects, 'Ingress'):
            for rule in ingress['spec']['rules']:
                for path in rule['http']['paths']:
                    self.assertEqual(path['pathType'], 'Prefix')
            self.assertNotIn('ingressClassName', ingress['spec'])

    def test_studio_body_limit_matches_production_nginx(self):
        middleware = named(self.objects, 'Middleware', 'studio-body-limit')
        self.assertEqual(middleware['spec']['buffering']['maxRequestBodyBytes'], 2048 * 1024 * 1024)
        annotation = named(self.objects, 'Ingress', 'studio')['metadata']['annotations']['traefik.ingress.kubernetes.io/router.middlewares']
        self.assertEqual(annotation, '%s-%s@kubernetescrd' % (LOCAL_NAMESPACE, middleware['metadata']['name']))
        for name in ('lms', 'static'):
            self.assertNotIn('traefik.ingress.kubernetes.io/router.middlewares', named(self.objects, 'Ingress', name)['metadata']['annotations'])

    def test_static_deployment_serves_the_image_tree_with_the_same_image(self):
        deployment = named(self.objects, 'Deployment', 'static')
        spec = deployment['spec']['template']['spec']
        init = spec['initContainers'][0]
        local_tag = named(self.base_objects, 'Deployment', 'lms')['spec']['template']['spec']['containers'][0]['image']
        self.assertEqual(init['image'], local_tag, 'the static tree must come from the very image the pods run')
        self.assertEqual(init['command'][-2:], ['/edx/var/edxapp/staticfiles/.', '/srv/www/static/'])
        nginx = spec['containers'][0]
        self.assertRegex(nginx['image'], r'^nginxinc/nginx-unprivileged:\d+\.\d+\.\d+-alpine$')
        self.assertEqual(nginx['ports'][0]['containerPort'], 8080)
        mounts = {m['mountPath']: m for m in nginx['volumeMounts']}
        self.assertTrue(mounts['/srv/www/static']['readOnly'])
        self.assertTrue(mounts['/etc/nginx/conf.d']['readOnly'])
        self.assertIn('/tmp', mounts)
        self.assertEqual(named(self.objects, 'Service', 'static')['spec']['ports'][0]['port'], 8080)

    def test_nginx_rules_match_the_production_static_rules(self):
        conf = (TRAEFIK_OVERLAY / 'ingress/nginx.conf').read_text()
        self.assertIn('listen 8080;', conf)
        self.assertIn('root /srv/www;', conf)
        self.assertRegex(conf, r'\^/static/\(studio/\)\?\[\^/\]\+\\\.\(json\|xml\)\$ \{ return 403; \}')
        self.assertIn('README\\.TXT', conf)
        self.assertIn('[0-9a-f]{12}', conf)
        self.assertIn('immutable', conf)
        self.assertNotIn('autoindex on', conf)
        configmap = [c for c in of_kind(self.objects, 'ConfigMap') if c['metadata']['name'].startswith('static-nginx-conf')]
        self.assertEqual(len(configmap), 1)
        self.assertEqual(configmap[0]['data']['default.conf'], conf)

    def test_every_application_pod_trusts_the_local_ca_bundle(self):
        checked = 0
        for objects in (self.objects, self.jobs):
            for kind, name, template in pod_templates(objects):
                if template['metadata']['labels'].get('app.kubernetes.io/name') != 'edxapp':
                    continue
                checked += 1
                volumes = {v['name']: v for v in template['spec']['volumes']}
                self.assertEqual(volumes['local-ca-bundle'], {'name': 'local-ca-bundle', 'configMap': {'name': 'local-ca-bundle'}}, name)
                for container in template['spec']['containers']:
                    env = {e['name']: e.get('value') for e in container['env']}
                    self.assertEqual(env['SSL_CERT_FILE'], CA_BUNDLE, name)
                    self.assertEqual(env['REQUESTS_CA_BUNDLE'], CA_BUNDLE, name)
                    mounts = {m['mountPath']: m for m in container['volumeMounts']}
                    self.assertTrue(mounts['/etc/local-ca']['readOnly'], name)
        self.assertGreaterEqual(checked, 2 + 2 + 3 + 1, 'lms, cms, workers, cron jobs and db-init')

    def test_other_containers_are_not_given_the_bundle(self):
        for kind, name, template in pod_templates(self.objects):
            if template['metadata']['labels'].get('app.kubernetes.io/name') == 'edxapp':
                continue
            for container in containers(template):
                names = {e['name'] for e in container.get('env', [])}
                self.assertFalse({'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE'} & names, name)
        es = named(self.objects, 'StatefulSet', 'elasticsearch')['spec']['template']['spec']['containers'][0]
        self.assertNotIn('local-ca-bundle', [m['name'] for m in es['volumeMounts']])

    def test_feature_objects_carry_the_label_and_the_rest_does_not(self):
        feature = {(o['kind'], o['metadata']['name']) for o in self.ingress_objects}
        for obj in self.ingress_objects:
            self.assertEqual(obj['metadata']['labels'][FEATURE_LABEL[0]], FEATURE_LABEL[1], obj['metadata']['name'])
        labelled = {(o['kind'], o['metadata']['name']) for o in self.objects
                    if o['metadata'].get('labels', {}).get(FEATURE_LABEL[0]) == FEATURE_LABEL[1]}
        self.assertEqual(labelled, feature)
        self.assertEqual({k for k, _ in feature}, {'Ingress', 'Middleware', 'Deployment', 'Service', 'ConfigMap'})

    def test_local_overlay_content_is_kept(self):
        base = {(o['kind'], o['metadata']['name']) for o in self.base_objects}
        overlay = {(o['kind'], o['metadata']['name']) for o in self.objects}
        self.assertTrue(base <= overlay)
        self.assertEqual(overlay - base, {('Ingress', 'lms'), ('Ingress', 'studio'), ('Ingress', 'static'),
                                          ('Middleware', 'studio-body-limit'), ('Deployment', 'static'), ('Service', 'static')}
                         | {(o['kind'], o['metadata']['name']) for o in self.ingress_objects if o['kind'] == 'ConfigMap'})

    def test_readiness_probes_keep_a_host_that_is_always_allowed(self):
        for name in ('lms', 'cms'):
            container = named(self.objects, 'Deployment', name)['spec']['template']['spec']['containers'][0]
            self.assertIn({'name': 'Host', 'value': 'localhost'}, container['readinessProbe']['httpGet']['httpHeaders'])

    def test_image_tag_is_the_one_of_the_local_overlay(self):
        pattern = re.compile(r'newTag:\s*(\S+)')
        tags = {pattern.search(p.read_text()).group(1) for p in (
            HERE / 'overlays/orbstack-local/kustomization.yaml', HERE / 'overlays/orbstack-local/jobs/kustomization.yaml',
            TRAEFIK_OVERLAY / 'ingress/kustomization.yaml')}
        self.assertEqual(len(tags), 1, tags)

    def test_coredns_rewrite_targets_the_traefik_service(self):
        text = (TRAEFIK_DIR / 'coredns-custom.yaml').read_text()
        self.assertIn('name: coredns-custom', text)
        self.assertIn('namespace: kube-system', text)
        self.assertIn('py313.learningtribes.com/feature: traefik-local', text)
        rule = [l.strip() for l in text.splitlines() if l.strip().startswith('rewrite stop name regex')]
        self.assertEqual(rule, [r'rewrite stop name regex ^(.*\.)?local-prod\.7mud\.com\.$ traefik.traefik.svc.cluster.local. answer auto'])
        self.assertEqual(text.count('.override: |'), 1)
        self.assertEqual(rule[0].split()[4], r'^(.*\.)?%s\.$' % BASE_DOMAIN.replace('.', r'\.'))

    def test_base_domain_is_defined_once_in_the_scripts_and_matches(self):
        self.assertIn('readonly BASE_DOMAIN=%s\n' % BASE_DOMAIN, (HERE / 'scripts/lib.sh').read_text())


if __name__ == '__main__':
    unittest.main()
