"""Local development schema from the complete LMS/CMS model union.

Historical migrations are intentionally disabled for every inventoried app.
They reference removed DOP and pre-Django-2 APIs. This is a fresh local model
schema, NOT a historical migration or a supported production upgrade path.
No historical migration is marked applied.
"""
import sys
from pathlib import Path

from startup_lms import *
# Contentstore model signal imports need the genuine Studio authoring defaults.
import cms.envs.common as _cms_common
for _key in dir(_cms_common):
    if _key.isupper() and _key not in globals():
        globals()[_key] = getattr(_cms_common, _key)

# CMS common adds this real app root during its normal startup.
sys.path.append(str(Path("/edx/app/edxapp/edx-platform/cms/djangoapps")))

INSTALLED_APPS = [*INSTALLED_APPS, *['method_override', 'contentstore.apps.ContentstoreConfig', 'xblock_config.apps.XBlockConfig', 'require', 'cms.lib.xblock.tagging', 'rules.apps.AutodiscoverRulesConfig', 'cms_user_tasks.apps.CmsUserTasksConfig', 'cms.djangoapps.api.apps.ApiConfig', 'pipeline_mako', 'rest_framework.authtoken']]
DATABASE_ROUTERS = []  # One isolated local database owns the complete union.
MIGRATION_MODULES = {'auth': None, 'contenttypes': None, 'humanize': None, 'messages': None, 'redirects': None, 'sessions': None, 'sites': None, 'staticfiles': None, 'common_initialization': None, 'lms_initialization': None, 'common_views': None, 'simple_history': None, 'config_models': None, 'waffle': None, 'service_status': None, 'status': None, 'edxmako': None, 'pipeline': None, 'static_replace': None, 'webpack_loader': None, 'web_fragments': None, 'plugin_api': None, 'contentserver': None, 'site_configuration': None, 'video_config': None, 'video_pipeline': None, 'courseware': None, 'student': None, 'static_template_view': None, 'staticbook': None, 'track': None, 'eventtracking_django': None, 'util': None, 'certificates': None, 'dashboard': None, 'instructor_task': None, 'course_groups': None, 'bulk_email': None, 'branding': None, 'oauth2_provider': None, 'oauth_dispatch': None, 'third_party_auth': None, 'auth_exchange': None, 'wiki': None, 'django_notify': None, 'course_wiki': None, 'mptt': None, 'sekizai': None, 'links': None, 'markdownedx': None, 'admin': None, 'debug': None, 'open_edx_util': None, 'django_comment_client': None, 'django_comment_common': None, 'discussion_api': None, 'notes': None, 'edxnotes': None, 'splash': None, 'datadog': None, 'rest_framework': None, 'user_api': None, 'extended_api': None, 'notification_prefs': None, 'notifier_api': None, 'course_modes': None, 'course': None, 'enrollment': None, 'verify_student': None, 'dark_lang': None, 'microsite_configuration': None, 'course_action_state': None, 'edx_jsme': None, 'django_countries': None, 'social_django': None, 'lms_xblock': None, 'submissions': None, 'openassessment': None, 'assessment': None, 'fileupload': None, 'workflow': None, 'xblock': None, 'edxval': None, 'course_overviews': None, 'course_structures': None, 'block_structure': None, 'course_blocks': None, 'mailing': None, 'corsheaders': None, 'cors_csrf': None, 'xblock_django': None, 'programs': None, 'program_enrollments': None, 'goodhabitz': None, 'catalog': None, 'self_paced': None, 'thumbnail': None, 'milestones': None, 'gating': None, 'statici18n': None, 'api_admin': None, 'verified_track_content': None, 'learner_dashboard': None, 'badges': None, 'django_sites_extensions': None, 'email_marketing': None, 'release_util': None, 'celery_utils': None, 'crawlers': None, 'database_fixups': None, 'waffle_utils': None, 'course_bookmarks': None, 'course_experience': None, 'course_search': None, 'learner_profile': None, 'learner_analytics': None, 'portfolio_project': None, 'django_filters': None, 'drf_yasg': None, 'triboo_analytics': None, 'django_tables2': None, 'user_tasks': None, 'edx_sga': None, 'edx_proctoring': None, 'organizations': None, 'ace_common': None, 'bookmarks': None, 'credentials': None, 'discussion': None, 'grades': None, 'instructor': None, 'password_policy': None, 'plugins': None, 'schedules': None, 'theming': None, 'lti_consumer': None, 'edx_when': None, 'edx_toggles': None, 'completion': None, 'method_override': None, 'contentstore': None, 'xblock_config': None, 'require': None, 'tagging': None, 'rules': None, 'cms_user_tasks': None, 'api': None, 'pipeline_mako': None, 'authtoken': None}
