"""Process-only LT-02 rejection settings; never used by retained HTTP services."""
from startup_lms import *

# Set before django.setup(), URL imports, backend registry and form SCOPES cache.
FEATURES = dict(FEATURES, ENABLE_THIRD_PARTY_AUTH=True)
AUTHENTICATION_BACKENDS = [
    *AUTHENTICATION_BACKENDS,
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.twitter.TwitterOAuth',
]
# Isolate configuration-model/ratelimit caches from the retained service cache.
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'py313-lt02-exchange-acceptance'}}
# ThirdPartyAuthConfig.ready appends the production exception middleware to
# MIDDLEWARE_CLASSES; Django 5.2 consumes MIDDLEWARE. Start both as one list.
MIDDLEWARE = list(MIDDLEWARE)
