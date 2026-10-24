"""Python 3.13 local CMS startup settings; no test mocks."""
from cms.envs.common import *
from local_runtime import configure
from openedx.core.lib.derived import derive_settings
configure(globals(), 'cms')
derive_settings(__name__)
