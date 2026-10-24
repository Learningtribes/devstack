"""Local startup configuration; fresh resources only, full platform app list."""
import os
import json
import tempfile
from pathlib import Path

def configure(namespace, system):
    platform_root = Path(os.environ.get('PY313_PLATFORM_ROOT', '/edx/app/edxapp/edx-platform'))
    # File XBlock expiration models must participate in the real app registry.
    if "djpyfs" not in namespace["INSTALLED_APPS"]:
        namespace["INSTALLED_APPS"] = [*namespace["INSTALLED_APPS"], "djpyfs"]
    namespace.update(
        DEBUG=False,
        MAKO_MODULE_DIR=os.path.join(tempfile.gettempdir(), f'mako_{system}_py313_{os.getpid()}'),
        ROOT_URLCONF='startup_' + system + '_urls',
        PROJECT_ROOT=str(platform_root),
        X_FRAME_OPTIONS='SAMEORIGIN',
        STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                  'staticfiles': {'BACKEND': 'openedx.core.storage.DevelopmentStorage'}},
        PIPELINE_ENABLED=False,  # Development serves each genuine vendor/Sass output.
        REQUIRE_DEBUG=True,  # RequireJS loads anonymous AMD sources; no optimizer build.
        CMS_SEGMENT_KEY=None,  # No external analytics account for isolated local runtime.
        WIKI_ENABLED=(system == 'lms'),  # Keep the locally testable course wiki route available.
        ALLOWED_HOSTS=['localhost', '127.0.0.1', 'lms', 'cms'],
        SECRET_KEY=os.environ['PY313_STARTUP_SECRET_KEY'],
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        DATABASE_ROUTERS=[],
        COMMON_TEST_DATA_ROOT=str(platform_root / 'common/test/data'),
        DATABASES={'default': {'ENGINE':'django.db.backends.mysql', 'NAME':os.environ.get('PY313_DATABASE_NAME', 'py313_startup_20261024'),
                   'USER':os.environ.get('PY313_MYSQL_USER','edxapp'), 'PASSWORD':os.environ['PY313_MYSQL_PASSWORD'],
                   'HOST':'mysql', 'PORT':'3306', 'OPTIONS':{'charset':'utf8mb4'},
                   'TEST': {'NAME':'py313_goal_scorm_test_20261025', 'CHARSET':None, 'COLLATION':None}}},
        CACHES={'default':{'BACKEND':'django.core.cache.backends.memcached.PyMemcacheCache',
                          'LOCATION':'memcached:11211','KEY_PREFIX':os.environ.get('PY313_CACHE_PREFIX', 'py313_startup_20261024')}},
        SESSION_ENGINE='django.contrib.sessions.backends.db',
        SESSION_SERIALIZER='django.contrib.sessions.serializers.JSONSerializer',
        SESSION_COOKIE_NAME='py313_startup_session',
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
        LMS_ROOT_URL=os.environ.get('PY313_LMS_ROOT_URL', 'http://localhost:18000'),
        CMS_ROOT_URL=os.environ.get('PY313_CMS_ROOT_URL', 'http://localhost:18010'),
        LMS_BASE=os.environ.get('PY313_LMS_DOMAIN', 'localhost:18000'),
        CMS_BASE=os.environ.get('PY313_CMS_DOMAIN', 'localhost:18010'),
        SITE_NAME=os.environ.get('PY313_LMS_DOMAIN', 'localhost:18000'),
        # Site primary keys are environment data. Resolve them from the
        # nonsecret domain-to-PK map emitted by natural-key site seeding.
        SITE_ID=namespace.get('SITE_ID', 1),
        STATIC_ROOT='/runtime/static/'+system, MEDIA_ROOT='/runtime/media',
        DJFS={'type': 'osfs', 'directory_root': '/runtime/media/djpyfs',
              'url_root': '/media/djpyfs'},
        DATA_DIR='/runtime/data',
        STUDIO_LOGS_COURSES_CSV_PATH='/runtime/logs/cms.csv',
        STUDIO_LOGS_COURSES_HISTORY_CSV_PATH='/runtime/logs/cms-history.csv',
        COMPREHENSIVE_THEME_DIRS=['/runtime/themes-7c0dbec1b0a7', str(platform_root / 'themes')],
        COMPREHENSIVE_THEME_LOCALE_PATHS=['/runtime/locale'],
        # Templates request the exact configured LANGUAGE_CODE, including LT
        # variants absent from Django's built-in language registry.
        STATICI18N_FILENAME_FUNCTION='statici18n.utils.legacy_filename',
        LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},
                 'root':{'handlers':['console'],'level':'INFO'}},
        # No local XQueue service is provisioned; external grading remains unverified.
        XQUEUE_INTERFACE={'url':'http://127.0.0.1:18040',
                          'django_auth':{'username':'startup-local', 'password':os.environ['PY313_STARTUP_XQUEUE_PASSWORD']},
                          'basic_auth':None},
        CELERY_TASK_ALWAYS_EAGER=False,
        CELERY_BROKER_URL=os.environ.get('PY313_CELERY_BROKER_URL', 'amqp://{user}:{password}@rabbitmq:5672//'.format(user=os.environ.get('PY313_RABBITMQ_USER', 'edxapp'), password=os.environ['PY313_RABBITMQ_PASSWORD'])),
        broker_url=os.environ.get('PY313_CELERY_BROKER_URL', 'amqp://{user}:{password}@rabbitmq:5672//'.format(user=os.environ.get('PY313_RABBITMQ_USER', 'edxapp'), password=os.environ['PY313_RABBITMQ_PASSWORD'])),
        BROKER_URL=os.environ.get('PY313_CELERY_BROKER_URL', 'amqp://{user}:{password}@rabbitmq:5672//'.format(user=os.environ.get('PY313_RABBITMQ_USER', 'edxapp'), password=os.environ['PY313_RABBITMQ_PASSWORD'])),
        CELERY_RESULT_BACKEND='cache+memcached://memcached:11211/',
    )
    site_map_path = Path('/runtime/config/site-ids.json')
    if site_map_path.is_file():
        site_ids = json.loads(site_map_path.read_text())
        site_domain = os.environ.get('PY313_LMS_DOMAIN', 'localhost:18000') if system == 'lms' else os.environ.get('PY313_CMS_DOMAIN', 'localhost:18010')
        namespace['SITE_ID'] = int(site_ids[site_domain])
    from local_discovery import configure as configure_discovery
    configure_discovery(namespace)
    queue_prefix = os.environ.get('PY313_TASK_QUEUE_PREFIX')
    if queue_prefix:
        queue_names = {priority: queue_prefix + '.' + priority
                       for priority in ('high', 'default', 'low', 'high_mem')}
        namespace.update(
            HIGH_PRIORITY_QUEUE=queue_names['high'],
            DEFAULT_PRIORITY_QUEUE=queue_names['default'],
            LOW_PRIORITY_QUEUE=queue_names['low'],
            HIGH_MEM_QUEUE=queue_names['high_mem'],
            CELERY_DEFAULT_QUEUE=queue_names['default'],
            CELERY_DEFAULT_ROUTING_KEY=queue_names['default'],
            CELERY_DEFAULT_EXCHANGE=queue_prefix,
            CELERY_QUEUES={name: {} for name in queue_names.values()},
            CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS={'global_keyprefix': queue_prefix + ':'},
        )
    # Exercise the canonical DOT routes in this isolated local runtime.
    namespace['FEATURES']['ENABLE_OAUTH2_PROVIDER'] = True
    namespace['FEATURES']['ENABLE_COURSEWARE_SEARCH'] = True
    namespace['FEATURES']['ENABLE_COURSEWARE_INDEX'] = True
    # Keep the local JWT contract usable without placing a signing secret in source.
    jwt_key_path = Path('/startup/jwt-private.pem')
    if jwt_key_path.is_file():
        jwt_private_key = jwt_key_path.read_text()
        jwt_issuer = 'http://localhost:18000/oauth2'
        jwt_audience = 'py313-local-lms'
        namespace.update(
            OAUTH_OIDC_ISSUER=jwt_issuer,
            DEFAULT_JWT_ISSUER={
                'ISSUER': jwt_issuer,
                'SECRET_KEY': namespace['SECRET_KEY'],
                'AUDIENCE': jwt_audience,
            },
            JWT_PRIVATE_SIGNING_KEY=jwt_private_key,
            JWT_EXPIRED_PRIVATE_SIGNING_KEYS=[],
        )
        # This isolated LMS is both issuer and consumer; no external IDA trusts
        # its signing key. Restricted claims are enforced by API permissions.
        namespace['RESTRICTED_APPLICATION_JWT_ISSUER'] = dict(namespace['DEFAULT_JWT_ISSUER'])
        namespace['JWT_AUTH'].update(
            JWT_ISSUERS=[namespace['DEFAULT_JWT_ISSUER']],
            JWT_ISSUER=jwt_issuer,
            JWT_AUDIENCE=jwt_audience,
            JWT_SECRET_KEY=namespace['SECRET_KEY'],
            # JwtBuilder signs client-specific JWT access tokens with the
            # configured secret; keep the platform's HS256 contract here.
            JWT_ALGORITHM='HS256',
        )
    namespace.update(SEARCH_ENGINE='search.elastic.ElasticSearchEngine',
                     ELASTIC_SEARCH_CONFIG=[{'host': 'elasticsearch', 'port': 9200, 'use_ssl': False}],
                     ELASTIC_SEARCH_INDEX_PREFIX=os.environ.get('PY313_ES_INDEX_PREFIX', 'py313_startup_20261024_'),
                     COURSEWARE_INDEX_NAME='courses', PROGRAM_INDEX_NAME='programs')
    # Same explicit fresh-schema contract as the initializer; no old graph loaded.
    inventory = json.loads(Path('/startup/schema-app-inventory.json').read_text())
    namespace['MIGRATION_MODULES'] = {entry['label']: None for entry in inventory['lms'] + inventory['cms']}
    namespace['WEBPACK_LOADER'] = {'DEFAULT': {'BUNDLE_DIR_NAME': 'bundles/', 'STATS_FILE': '/runtime/static/' + system + '/webpack-stats.json'}}
    namespace['MIDDLEWARE']=list(namespace['MIDDLEWARE_CLASSES'])
    mongo=dict(namespace['DOC_STORE_CONFIG'],host='mongo',port=27017,db=os.environ.get('PY313_MONGO_DB', 'py313_startup_20261024'),
               user=os.environ.get('PY313_MONGO_USER','edxapp'),password=os.environ['PY313_MONGO_PASSWORD'],authSource='admin')
    namespace['DOC_STORE_CONFIG']=mongo
    # LT program objects use their own collections but must share this isolated
    # environment's authenticated database, never the common.py devstack host.
    namespace['EDX_OBJECTS_MONGODB_SETTINGS'] = {
        name: {key: mongo[key] for key in ('host', 'port', 'db', 'user', 'password', 'authSource')}
        for name in namespace['EDX_OBJECTS_MONGODB_SETTINGS']
    }
    namespace['CONTENTSTORE'] = {
        'ENGINE': 'xmodule.contentstore.mongo.MongoContentStore',
        'DOC_STORE_CONFIG': dict(mongo),
        'ADDITIONAL_OPTIONS': {'trashcan': {'bucket': 'trash_fs'}},
    }
    for store in namespace['MODULESTORE']['default']['OPTIONS']['stores']:
        store['DOC_STORE_CONFIG']=dict(mongo)
