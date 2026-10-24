"""Python 3.13 local LMS startup settings; no test mocks."""
from lms.envs.common import *
from local_runtime import configure
from openedx.core.lib.derived import derive_settings
configure(globals(), 'lms')
derive_settings(__name__)
