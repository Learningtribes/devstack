"""Real app gates and authentication diagnostics, no external service calls."""
import base64
import logging
from types import SimpleNamespace
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from student.views.admin_panel import AdminPanel
from openedx.core.djangoapps.oauth_dispatch.dot_overrides.validators import EdxOAuth2Validator
from openedx.core.djangoapps.safe_sessions.middleware import SafeCookieData, SafeCookieError

factory = RequestFactory()
request = factory.get('/admin_panel/users')
request.user = AnonymousUser()
assert AdminPanel().dispatch(request).status_code == 302
for active in (False, True):
    request.user = SimpleNamespace(is_authenticated=True, is_active=active, is_staff=False)
    try:
        AdminPanel().dispatch(request)
    except PermissionDenied:
        pass
    else:
        raise AssertionError('Nonstaff admin access accepted')
print('PASS anonymous login redirect and authenticated nonstaff admin denial')

class Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []
    def emit(self, record):
        self.messages.append(record.getMessage())

records = Records()
loggers = [logging.getLogger('openedx.core.djangoapps.oauth_dispatch.dot_overrides.validators'),
           logging.getLogger('openedx.core.djangoapps.safe_sessions.middleware')]
for logger in loggers:
    logger.addHandler(records)
try:
    validator = EdxOAuth2Validator()
    for raw in ['private-credential-!not-base64', base64.b64encode(b'private-credential-no-colon').decode(), base64.b64encode(b'\xffprivate-credential').decode()]:
        oauth_request = SimpleNamespace(headers={'HTTP_AUTHORIZATION': 'Basic '+raw, 'Authorization': 'Basic '+raw}, encoding='utf-8')
        assert validator._authenticate_basic_auth(oauth_request) is False
    marker = 'private-cookie-identifier'
    try:
        SafeCookieData.parse(marker)
    except SafeCookieError as error:
        assert marker not in str(error)
    else:
        raise AssertionError('Malformed cookie accepted')
    assert not any('private-credential' in message or marker in message for message in records.messages)
finally:
    for logger in loggers:
        logger.removeHandler(records)
print('PASS malformed Basic credentials fail closed; credential/cookie diagnostics redacted')
