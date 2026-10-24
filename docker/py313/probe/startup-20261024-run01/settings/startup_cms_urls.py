"""Local CMS URL extensions for media-backed course content."""
import re

from django.conf import settings
from django.urls import re_path
from django.views.static import serve

from cms.urls import urlpatterns as platform_urlpatterns

urlpatterns = list(platform_urlpatterns)
media_prefix = re.escape(settings.MEDIA_URL.lstrip('/'))
urlpatterns.append(re_path(
    r'^' + media_prefix + r'(?P<path>.*)$',
    serve,
    {'document_root': settings.MEDIA_ROOT},
))
