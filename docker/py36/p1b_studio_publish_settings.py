# -*- coding: utf-8 -*-
"""Shared settings for the isolated Studio edit/publish browser gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os

from search.tests.mock_search_engine import MockSearchEngine
from xmodule.modulestore.modulestore_settings import update_module_store_settings


_XMODULE_ENTRY_POINTS = {
    # The Py2 rollback image does not carry the source-tree distribution
    # metadata used by stevedore for the platform's course tabs.
    'openedx.course_tab': (
        'courseware = lms.djangoapps.courseware.tabs:CoursewareTab',
        'course_info = lms.djangoapps.courseware.tabs:CourseInfoTab',
        'discussion = lms.djangoapps.discussion.plugins:DiscussionTab',
        'edxnotes = lms.djangoapps.edxnotes.plugins:EdxNotesTab',
        'external_discussion = lms.djangoapps.courseware.tabs:ExternalDiscussionCourseTab',
        'external_link = lms.djangoapps.courseware.tabs:ExternalLinkCourseTab',
        'html_textbooks = lms.djangoapps.courseware.tabs:HtmlTextbookTabs',
        'instructor = lms.djangoapps.instructor.views.instructor_dashboard:InstructorDashboardTab',
        'notes = lms.djangoapps.notes.views:NotesTab',
        'pdf_textbooks = lms.djangoapps.courseware.tabs:PDFTextbookTabs',
        'progress = lms.djangoapps.courseware.tabs:ProgressTab',
        'static_tab = xmodule.tabs:StaticTab',
        'syllabus = lms.djangoapps.courseware.tabs:SyllabusTab',
        'teams = lms.djangoapps.teams.plugins:TeamsTab',
        'textbooks = lms.djangoapps.courseware.tabs:TextbookTabs',
        'wiki = lms.djangoapps.course_wiki.tab:WikiTab',
    ),
    'xblock.v1': (
        'book = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'chapter = xmodule.seq_module:SectionDescriptor',
        'conditional = xmodule.conditional_module:ConditionalDescriptor',
        'course = xmodule.course_module:CourseDescriptor',
        'customtag = xmodule.template_module:CustomTagDescriptor',
        'discuss = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'html = xmodule.html_module:HtmlDescriptor',
        'image = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'library_content = xmodule.library_content_module:LibraryContentDescriptor',
        'error = xmodule.error_module:ErrorDescriptor',
        'poll_question = xmodule.poll_module:PollDescriptor',
        'problem = xmodule.capa_module:CapaDescriptor',
        'problemset = xmodule.seq_module:SequenceDescriptor',
        'randomize = xmodule.randomize_module:RandomizeDescriptor',
        'split_test = xmodule.split_test_module:SplitTestDescriptor',
        'section = xmodule.backcompat_module:SemanticSectionDescriptor',
        'sequential = xmodule.seq_module:SequenceDescriptor',
        'slides = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'video = xmodule.video_module:VideoDescriptor',
        'videoalpha = xmodule.video_module:VideoDescriptor',
        'videodev = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'videosequence = xmodule.seq_module:SequenceDescriptor',
        'course_info = xmodule.html_module:CourseInfoDescriptor',
        'static_tab = xmodule.html_module:StaticTabDescriptor',
        'custom_tag_template = xmodule.raw_module:RawDescriptor',
        'about = xmodule.html_module:AboutDescriptor',
        'annotatable = xmodule.annotatable_module:AnnotatableDescriptor',
        'textannotation = xmodule.textannotation_module:TextAnnotationDescriptor',
        'videoannotation = xmodule.videoannotation_module:VideoAnnotationDescriptor',
        'imageannotation = xmodule.imageannotation_module:ImageAnnotationDescriptor',
        'word_cloud = xmodule.word_cloud_module:WordCloudDescriptor',
        'hidden = xmodule.hidden_module:HiddenDescriptor',
        'raw = xmodule.raw_module:RawDescriptor',
        'lti = xmodule.lti_module:LTIDescriptor',
        'preference = xmodule.preference_module:StudentPreferenceDescriptor',
        'library = xmodule.library_root_xblock:LibraryRoot',
        'vertical = xmodule.vertical_block:VerticalBlock',
        'wrapper = xmodule.wrapper_module:WrapperBlock',
    ),
    'xmodule.v1': (
        'book = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'chapter = xmodule.seq_module:SectionDescriptor',
        'conditional = xmodule.conditional_module:ConditionalDescriptor',
        'course = xmodule.course_module:CourseDescriptor',
        'customtag = xmodule.template_module:CustomTagDescriptor',
        'discuss = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'html = xmodule.html_module:HtmlDescriptor',
        'image = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'library_content = xmodule.library_content_module:LibraryContentDescriptor',
        'error = xmodule.error_module:ErrorDescriptor',
        'poll_question = xmodule.poll_module:PollDescriptor',
        'problem = xmodule.capa_module:CapaDescriptor',
        'problemset = xmodule.seq_module:SequenceDescriptor',
        'randomize = xmodule.randomize_module:RandomizeDescriptor',
        'split_test = xmodule.split_test_module:SplitTestDescriptor',
        'section = xmodule.backcompat_module:SemanticSectionDescriptor',
        'sequential = xmodule.seq_module:SequenceDescriptor',
        'slides = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'video = xmodule.video_module:VideoDescriptor',
        'videoalpha = xmodule.video_module:VideoDescriptor',
        'videodev = xmodule.backcompat_module:TranslateCustomTagDescriptor',
        'videosequence = xmodule.seq_module:SequenceDescriptor',
        'course_info = xmodule.html_module:CourseInfoDescriptor',
        'static_tab = xmodule.html_module:StaticTabDescriptor',
        'custom_tag_template = xmodule.raw_module:RawDescriptor',
        'about = xmodule.html_module:AboutDescriptor',
        'annotatable = xmodule.annotatable_module:AnnotatableDescriptor',
        'textannotation = xmodule.textannotation_module:TextAnnotationDescriptor',
        'videoannotation = xmodule.videoannotation_module:VideoAnnotationDescriptor',
        'imageannotation = xmodule.imageannotation_module:ImageAnnotationDescriptor',
        'word_cloud = xmodule.word_cloud_module:WordCloudDescriptor',
        'hidden = xmodule.hidden_module:HiddenDescriptor',
        'raw = xmodule.raw_module:RawDescriptor',
        'lti = xmodule.lti_module:LTIDescriptor',
        'preference = xmodule.preference_module:StudentPreferenceDescriptor',
    ),
    'xblock_asides.v1': (
        'tagging_aside = cms.lib.xblock.tagging:StructuredTagsAside',
    ),
}


# The Py2 rollback image also lacks the Platform distribution metadata used by
# stevedore for block-structure transformers.  Course home asks for these
# transformers while rendering learner progress.
_PLATFORM_ENTRY_POINTS = {
    'lms.djangoapp': (
        'bookmarks = openedx.core.djangoapps.bookmarks.apps:BookmarksConfig',
        'edx_proctoring = edx_proctoring.apps:EdxProctoringConfig',
        'grades = lms.djangoapps.grades.apps:GradesConfig',
        'theming = openedx.core.djangoapps.theming.apps:ThemingConfig',
    ),
    'cms.djangoapp': (
        'bookmarks = openedx.core.djangoapps.bookmarks.apps:BookmarksConfig',
        'edx_proctoring = edx_proctoring.apps:EdxProctoringConfig',
        'theming = openedx.core.djangoapps.theming.apps:ThemingConfig',
    ),
    'openedx.block_structure_transformer': (
        'library_content = lms.djangoapps.course_blocks.transformers.library_content:ContentLibraryTransformer',
        'split_test = lms.djangoapps.course_blocks.transformers.split_test:SplitTestTransformer',
        'start_date = lms.djangoapps.course_blocks.transformers.start_date:StartDateTransformer',
        'user_partitions = lms.djangoapps.course_blocks.transformers.user_partitions:UserPartitionTransformer',
        'visibility = lms.djangoapps.course_blocks.transformers.visibility:VisibilityTransformer',
        'hidden_content = lms.djangoapps.course_blocks.transformers.hidden_content:HiddenContentTransformer',
        'course_blocks_api = lms.djangoapps.course_api.blocks.transformers.blocks_api:BlocksAPITransformer',
        'milestones = lms.djangoapps.course_api.blocks.transformers.milestones:MilestonesAndSpecialExamsTransformer',
        'grades = lms.djangoapps.grades.transformer:GradesTransformer',
        'completion = lms.djangoapps.course_api.blocks.transformers.block_completion:BlockCompletionTransformer',
        'load_override_data = lms.djangoapps.course_blocks.transformers.load_override_data:OverrideDataTransformer',
    ),
}


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('{} is required'.format(name))
    return value


class P1BMockSearchEngine(MockSearchEngine):
    """Adapt the legacy mock to the search API's production filter shape."""

    @staticmethod
    def _unwrap_filter_dictionary(filters):
        unwrapped = {}
        for field_name, value in (filters or {}).items():
            if isinstance(value, dict) and 'value' in value:
                unwrapped[field_name] = value['value']
            else:
                unwrapped[field_name] = value
        return unwrapped

    def search(self, *args, **kwargs):
        kwargs['filter_dictionary'] = self._unwrap_filter_dictionary(
            kwargs.get('filter_dictionary')
        )
        query_strings = kwargs.pop('query_strings', None)
        if query_strings:
            if isinstance(query_strings, (list, tuple, set)):
                query_strings = ' '.join(sorted(query_strings))
            kwargs['query_string'] = query_strings
        results = super(P1BMockSearchEngine, self).search(*args, **kwargs)
        # The legacy mock nests the course id in data, while Studio's discovery
        # response decorator reads the production engine's top-level `_id`.
        for result in results.get('results', ()):
            if '_id' not in result and result.get('data', {}).get('id'):
                result['_id'] = result['data']['id']
        return results


def _register_legacy_xmodule_metadata(namespace):
    """Restore source-tree XModule entry points in the Py2 rollback image."""
    import pkg_resources
    import xmodule

    if list(pkg_resources.iter_entry_points('xblock.v1', 'course')):
        return

    source_root = os.path.dirname(os.path.dirname(xmodule.__file__))
    metadata_root = os.path.join('/tmp', namespace, 'XModule.egg-info')
    if not os.path.isdir(metadata_root):
        os.makedirs(metadata_root)
    metadata_files = {
        'PKG-INFO': 'Metadata-Version: 1.0\nName: XModule\nVersion: 0.1.1\n',
        'top_level.txt': 'xmodule\n',
        'entry_points.txt': '\n\n'.join(
            '\n'.join(['[{}]'.format(group)] + list(entries))
            for group, entries in _XMODULE_ENTRY_POINTS.items()
        ) + '\n',
    }
    for filename, contents in metadata_files.items():
        path = os.path.join(metadata_root, filename)
        if not os.path.exists(path):
            with open(path, 'w') as metadata_file:
                metadata_file.write(contents)
    distribution = pkg_resources.Distribution(
        project_name='XModule',
        version='0.1.1',
        location=source_root,
        metadata=pkg_resources.PathMetadata(source_root, metadata_root),
    )
    pkg_resources.working_set.add(distribution)


def _register_legacy_platform_metadata(namespace, service):
    """Restore Platform entry points absent from the Py2 rollback image."""
    import openedx
    import pkg_resources

    project_type = 'lms.djangoapp' if service == 'lms' else 'cms.djangoapp'
    if list(pkg_resources.iter_entry_points(project_type, 'bookmarks')):
        return

    source_root = os.path.dirname(os.path.dirname(openedx.__file__))
    metadata_root = os.path.join('/tmp', namespace, 'Open_edX.egg-info')
    if not os.path.isdir(metadata_root):
        os.makedirs(metadata_root)
    metadata_files = {
        'PKG-INFO': 'Metadata-Version: 1.0\nName: Open edX\nVersion: 0.11\n',
        'top_level.txt': 'cms\nlms\nopenedx\n',
        'entry_points.txt': '\n\n'.join(
            '\n'.join(['[{}]'.format(group)] + list(entries))
            for group, entries in _PLATFORM_ENTRY_POINTS.items()
        ) + '\n',
    }
    for filename, contents in metadata_files.items():
        path = os.path.join(metadata_root, filename)
        with open(path, 'w') as metadata_file:
            metadata_file.write(contents)
    distribution = pkg_resources.Distribution(
        project_name='Open edX',
        version='0.11',
        location=source_root,
        metadata=pkg_resources.PathMetadata(source_root, metadata_root),
    )
    pkg_resources.working_set.add(distribution)

    # The settings import asks the plugin registry for apps before this
    # fallback metadata is registered.  Drop that stale result so URL discovery
    # sees the restored entry points in the same process.
    from stevedore.extension import ExtensionManager
    from openedx.core.djangoapps.plugins import registry
    ExtensionManager.ENTRY_POINT_CACHE.pop(project_type, None)
    registry.DjangoAppRegistry.get_available_plugins.cache.clear()


def configure(scope, service):
    """Apply the runtime contract to an imported LMS or CMS settings module."""
    prefix = 'PY36_R1_STUDIO_'
    runtime = _required(prefix + 'RUNTIME')
    namespace = _required(prefix + 'NAMESPACE')
    asset_dir = _required(prefix + 'ASSET_DIR')
    data_dir = _required(prefix + 'DATA_DIR')
    cache_container = _required(prefix + 'CACHE_CONTAINER')
    mongo_container = _required(prefix + 'MONGO_CONTAINER')
    mongo_module_store = _required(prefix + 'MONGO_MODULESTORE_DATABASE')
    mongo_content_store = _required(prefix + 'MONGO_CONTENTSTORE_DATABASE')
    mongo_user = _required(prefix + 'MONGO_USER')
    mongo_password = _required(prefix + 'MONGO_PASSWORD')
    sql_database = _required(prefix + 'SQL_DATABASE')
    sql_history_database = _required(prefix + 'SQL_HISTORY_DATABASE')
    sql_user = _required(prefix + 'SQL_USER')
    sql_password = _required(prefix + 'SQL_PASSWORD')
    cms_root_url = _required(prefix + 'CMS_ROOT_URL')
    lms_root_url = _required(prefix + 'LMS_ROOT_URL')
    lms_internal_root_url = _required(prefix + 'LMS_INTERNAL_ROOT_URL')
    secret_key = _required(prefix + 'SECRET_KEY')
    site_id = int(_required(prefix + 'SITE_ID_' + service.upper()))
    _register_legacy_xmodule_metadata(namespace)
    _register_legacy_platform_metadata(namespace, service)

    cms_base = cms_root_url.split('://', 1)[-1]
    lms_base = lms_root_url.split('://', 1)[-1]
    scope['STUDIO_RUNTIME'] = runtime
    scope['STUDIO_NAMESPACE'] = namespace
    scope['CMS_BASE'] = cms_base
    scope['CMS_ROOT_URL'] = cms_root_url
    scope['LMS_BASE'] = lms_base
    scope['LMS_ROOT_URL'] = lms_root_url
    scope['LMS_INTERNAL_ROOT_URL'] = lms_internal_root_url
    scope['SITE_NAME'] = cms_base if service == 'cms' else lms_base
    scope['SECRET_KEY'] = secret_key
    scope['SITE_ID'] = site_id
    scope['ALLOWED_HOSTS'] = sorted(set(list(scope.get('ALLOWED_HOSTS', ())) + [
        'localhost', '127.0.0.1', cms_base.split(':', 1)[0], lms_base.split(':', 1)[0],
    ]))

    features = copy.deepcopy(scope.get('FEATURES', {}))
    features.update({
        'ALLOW_AUTOMATED_SIGNUPS': False,
        'ALLOW_PUBLIC_ACCOUNT_CREATION': False,
        'AUTOMATIC_AUTH_FOR_TESTING': False,
        'COURSES_ARE_BROWSABLE': True,
        'ENABLE_COURSE_DISCOVERY': False,
        'ENABLE_COURSEWARE_INDEX': False,
        'ENABLE_COURSEWARE_SEARCH': False,
        'ENABLE_DISCUSSION_SERVICE': False,
        'ENABLE_LIBRARY_INDEX': False,
        'ENABLE_LAST_ACTIVITY': True,
        'ENABLE_THIRD_PARTY_AUTH': False,
        'RESTRICT_AUTOMATIC_AUTH': True,
        # Keep the normal learner host out of preview mode.  Preview mode
        # denies non-staff courseware access and is reserved for a separate
        # draft-preview hostname.
        'PREVIEW_LMS_BASE': 'preview.{}'.format(lms_base.split(':', 1)[0]),
    })
    scope['FEATURES'] = features

    scope['INSTALLED_APPS'] = [
        app for app in list(scope.get('INSTALLED_APPS', ())) if app != 'debug_toolbar'
    ]
    fallback_apps = (
        'openedx.core.djangoapps.bookmarks.apps.BookmarksConfig',
        'openedx.core.djangoapps.theming.apps.ThemingConfig',
        'edx_proctoring.apps.EdxProctoringConfig',
    )
    if service == 'lms':
        # The Py2 rollback image lacks the platform entry-point metadata that
        # normally registers GradesConfig and its migrations.
        fallback_apps += ('lms.djangoapps.grades.apps.GradesConfig',)
    for fallback_app in fallback_apps:
        if not any(fallback_app.split('.apps', 1)[0] in app for app in scope['INSTALLED_APPS']):
            scope['INSTALLED_APPS'].append(fallback_app)
    middleware = list(scope.get('MIDDLEWARE_CLASSES', ()))
    scope['MIDDLEWARE_CLASSES'] = [
        item for item in middleware if item not in (
            'django_comment_client.utils.QueryCountDebugMiddleware',
            'debug_toolbar.middleware.DebugToolbarMiddleware',
        )
    ]

    scope['DATABASES'] = copy.deepcopy(scope['DATABASES'])
    for alias, database in scope['DATABASES'].items():
        database.update({
            'ENGINE': 'django.db.backends.mysql',
            'USER': sql_user,
            'PASSWORD': sql_password,
            'HOST': 'edx.devstack.mysql',
            'PORT': '3306',
            'CONN_MAX_AGE': 0,
            'NAME': sql_history_database if alias == 'student_module_history' else sql_database,
        })

    scope['DOC_STORE_CONFIG'] = copy.deepcopy(scope.get('DOC_STORE_CONFIG', {}))
    scope['DOC_STORE_CONFIG'].update({
        'db': mongo_module_store,
        'host': [mongo_container],
        'user': mongo_user,
        'password': mongo_password,
    })
    scope['MODULESTORE'] = copy.deepcopy(scope['MODULESTORE'])
    update_module_store_settings(
        scope['MODULESTORE'],
        doc_store_settings={
            'db': mongo_module_store,
            'host': [mongo_container],
            'user': mongo_user,
            'password': mongo_password,
        },
        module_store_options={'fs_root': data_dir},
    )
    scope['MODULESTORE_BRANCH'] = 'draft-preferred' if service == 'cms' else 'published-only'
    scope['CONTENTSTORE'] = {
        'ENGINE': 'xmodule.contentstore.mongo.MongoContentStore',
        'DOC_STORE_CONFIG': {
            'db': mongo_content_store,
            'host': [mongo_container],
            'port': 27017,
            'user': mongo_user,
            'password': mongo_password,
        },
    }
    inheritance = copy.deepcopy(scope.get('MONGO_METADATA_INHERITANCE', {}))
    if isinstance(inheritance, dict):
        inheritance.update({
            'host': [mongo_container],
            'db': mongo_module_store,
            'user': mongo_user,
            'password': mongo_password,
        })
    scope['MONGO_METADATA_INHERITANCE'] = inheritance

    scope['CACHES'] = copy.deepcopy(scope.get('CACHES', {}))
    for alias, cache in scope['CACHES'].items():
        cache['BACKEND'] = 'django.core.cache.backends.memcached.MemcachedCache'
        cache['LOCATION'] = ['{}:11211'.format(cache_container)]
        cache['KEY_PREFIX'] = '{}_{}'.format(namespace, alias)
    scope['SESSION_ENGINE'] = 'django.contrib.sessions.backends.cached_db'
    scope['SESSION_CACHE_ALIAS'] = 'default'
    scope['SESSION_COOKIE_DOMAIN'] = None
    scope['SESSION_COOKIE_NAME'] = '{}_sessionid'.format(namespace)
    # The legacy LMS login form's JavaScript reads the conventional cookie
    # name directly; keep it compatible while each browser attempt uses a
    # fresh context and the session cookie remains runtime-scoped.
    scope['CSRF_COOKIE_NAME'] = 'csrftoken'
    scope['SESSION_COOKIE_SECURE'] = False
    scope['CSRF_COOKIE_SECURE'] = False
    scope['SESSION_COOKIE_HTTPONLY'] = True
    scope['CSRF_COOKIE_HTTPONLY'] = False

    scope['CELERY_ALWAYS_EAGER'] = True
    scope['CELERY_TASK_ALWAYS_EAGER'] = True
    scope['BROKER_URL'] = 'memory://'
    scope['CELERY_BROKER_URL'] = 'memory://'
    scope['CELERY_RESULT_BACKEND'] = 'cache+memcached://{}'.format(cache_container)
    scope['CELERY_DEFAULT_QUEUE'] = '{}.default'.format(namespace)
    scope['CELERY_DEFAULT_ROUTING_KEY'] = scope['CELERY_DEFAULT_QUEUE']
    scope['CELERY_QUEUES'] = {}
    low_priority_queue = scope.get('LOW_PRIORITY_QUEUE', '{}.low'.format(namespace))
    for routing_name in (
            'RECALCULATE_GRADES_ROUTING_KEY',
            'RECALCULATE_PROGRESS_ROUTING_KEY',
            'POLICY_CHANGE_GRADES_ROUTING_KEY'):
        scope.setdefault(routing_name, low_priority_queue)

    scope['DATA_DIR'] = data_dir
    scope['COURSES_ROOT'] = data_dir
    scope['GIT_REPO_DIR'] = os.path.join(data_dir, 'course_repos')
    scope['MEDIA_ROOT'] = os.path.join(data_dir, 'uploads')
    scope['FILE_UPLOAD_TEMP_DIR'] = os.path.join(data_dir, 'uploads')
    scope['STATUS_MESSAGE_PATH'] = os.path.join(data_dir, 'status_message.json')

    collected_static_root = asset_dir
    scope['COLLECTED_STATIC_ROOT'] = collected_static_root
    scope['STATIC_ROOT'] = os.path.join('/tmp', namespace, 'staticfiles-output')
    scope['STATIC_URL'] = '/static/'
    scope['STATICFILES_DIRS'] = [collected_static_root] + list(scope.get('STATICFILES_DIRS', ()))
    webpack_loader = copy.deepcopy(scope.get('WEBPACK_LOADER', {}))
    if 'DEFAULT' in webpack_loader:
        webpack_loader['DEFAULT']['STATS_FILE'] = os.path.join(asset_dir, 'webpack-stats.json')
    scope['WEBPACK_LOADER'] = webpack_loader

    scope['EMAIL_BACKEND'] = 'django.core.mail.backends.locmem.EmailBackend'
    scope['DEFAULT_FILE_STORAGE'] = 'django.core.files.storage.FileSystemStorage'
    scope['COURSE_IMPORT_EXPORT_STORAGE'] = 'django.core.files.storage.FileSystemStorage'
    scope['USER_TASKS_ARTIFACT_STORAGE'] = 'django.core.files.storage.FileSystemStorage'
    scope['LMS_ENROLLMENT_API_PATH'] = '/api/enrollment/v1/'
    scope['LOGIN_URL'] = '/signin' if service == 'cms' else '/login'
    scope['LOGIN_REDIRECT_URL'] = '/dashboard' if service == 'lms' else '/home/'
    scope['ENABLE_MKTG_SITE'] = False
    # Route disabled forum lookups to this LMS so the legacy client receives a
    # handled 404 instead of an uncaught connection-refused exception.
    scope['COMMENTS_SERVICE_URL'] = 'http://localhost:18000'
    scope['SEARCH_ENGINE'] = 'p1b_studio_publish_settings.P1BMockSearchEngine'
    scope['MOCK_SEARCH_BACKING_FILE'] = os.path.join(data_dir, 'mock-search-index.json')
    scope['HEARTBEAT_CHECKS'] = [
        check for check in scope.get('HEARTBEAT_CHECKS', ())
        if not check.endswith('.check_elasticsearch')
    ]
    scope['DEBUG'] = True
