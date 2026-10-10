# -*- coding: utf-8 -*-
"""E6 dev-server WSGI entry: /static/ from STATIC_ROOT_BASE ahead of Django.

Production nginx answers /static/ before Django on both the LMS and the Studio
host, from the shared collected tree (STATIC_ROOT_BASE; Studio's STATIC_ROOT is
its studio/ subdirectory). Studio pages depend on that: the theme's fonts
partial and common/static/css/noto-sans.css reference /static/css/ and
/static/fonts/ absolutely, outside Studio's /static/studio/ STATIC_URL.

Through the URLconf `static()` route every asset request runs the middleware
stack and its MySQL queries, and Django 1.11 hands `FileResponse` bodies to
`wsgi.file_wrapper` without ever closing the response, so `request_finished`
never fires and each request thread's connections stay open until cyclic GC.
A page's burst of asset requests then exhausts `max_connections`.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application
from django.views.static import serve

NGINX_STATIC_URL = '/static/'


class CollectedStaticHandler(StaticFilesHandler):
    """Serve /static/<path> from STATIC_ROOT_BASE/<path> with the URLconf route's view."""

    def get_base_url(self):
        return NGINX_STATIC_URL

    def serve(self, request):
        return serve(request, request.path[len(NGINX_STATIC_URL):], document_root=settings.STATIC_ROOT_BASE)


application = CollectedStaticHandler(get_wsgi_application())
