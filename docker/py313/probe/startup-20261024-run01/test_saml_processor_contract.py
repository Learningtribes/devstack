"""Offline installed-source contract, no IdP, request auth, or identity mocks."""
from django.conf import settings
settings.configure(SECRET_KEY='offline-contract-placeholder', SAML_IDP_SPCONFIG={},
                   INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes'])
import django
django.setup()
from django.contrib.auth.models import User
from djangosaml2idp.processors import BaseProcessor
from djangosaml2idp.views import get_processor

user = User(username='offline-unsaved', id=17)
for config in ({}, {'processor': 'djangosaml2idp.processors.BaseProcessor'}):
    processor = get_processor(config)
    assert isinstance(processor, BaseProcessor)
    assert processor.has_access(user) is True
    assert processor.create_identity(user, {'uid': 'id', 'username': 'username'}) == {
        'uid': 17, 'username': 'offline-unsaved'}
try:
    get_processor({'processor': 'djangosaml2idp.processors.DoesNotExist'})
except ImportError:
    pass
else:
    raise AssertionError('Invalid processor configuration was swallowed')
assert user.pk == 17 and user._state.adding
print('PASS installed default/custom processor instances and identity method signatures; no IdP or SQL')
