
from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r'^sso/post', views.sso_entry, name="saml_login_post"),
    re_path(r'^sso/redirect', views.sso_entry, name="saml_login_redirect"),
    re_path(r'^login/process/$', views.login_process, name='saml_login_process'),
    re_path(r'^metadata/$', views.metadata, name='saml2_idp_metadata'),
]
