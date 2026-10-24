from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import LoginView

from .forms import AuthenticationForm


def login(request, template_name='registration/login.html',
          redirect_field_name=REDIRECT_FIELD_NAME,
          authentication_form=AuthenticationForm,
          current_app=None, extra_context=None):
    """Use Django's CSRF-protected login and safe redirect validation."""
    request.current_app = current_app
    return LoginView.as_view(
        template_name=template_name,
        redirect_field_name=redirect_field_name,
        authentication_form=authentication_form,
        extra_context=extra_context,
    )(request)
