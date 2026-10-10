# -*- coding: utf-8 -*-
"""E6 dev-server WSGI entry: /static/ from STATIC_ROOT ahead of Django.

Production nginx answers /static/ from STATIC_ROOT before Django. Through the
URLconf `static()` route every asset request runs the middleware stack and its
MySQL queries, and Django 1.11 hands `FileResponse` bodies to
`wsgi.file_wrapper` without ever closing the response, so `request_finished`
never fires and each request thread's connections stay open until cyclic GC.
A page's burst of asset requests then exhausts `max_connections`.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application
from django.views.static import serve


class CollectedStaticHandler(StaticFilesHandler):
    """Serve STATIC_URL from STATIC_ROOT with the same view as the URLconf route."""

    def serve(self, request):
        return serve(request, request.path[len(self.base_url[2]):], document_root=settings.STATIC_ROOT)


application = CollectedStaticHandler(get_wsgi_application())
