"""LT multipart File editor on the current XBlock editing/validation API.

File metadata and editor resources originate from LT xblock-utils f3cc1bb954c7.
Keep upstream submit_studio_edits validation and runtime handler permissions.
"""
from web_fragments.fragment import Fragment
from xblock.fields import Scope
from xblock.utils.resources import ResourceLoader
from xblock.utils.studio_editable import StudioEditableXBlockMixin as BaseEditor

from .fields import File

loader = ResourceLoader(__name__)


class StudioEditableXBlockMixin(BaseEditor):
    """Preserve LT File/readonly controls without replacing upstream validation."""

    def _make_field_info(self, field_name, field):
        info = super()._make_field_info(field_name, field)
        if info is None:
            return None
        info['is_readonly'] = field.runtime_options.get('readonly', False)
        if isinstance(field, File):
            info.update(type='file', is_set=False, accept=field.accept,
                        extra_description=self.ugettext(field.extra_description),
                        optional_values=[])
            if field_name + 's' in self.fields:
                info['optional_values'] = self.fields[field_name + 's'].read_from(self)
        return info

    def studio_view(self, context):
        fields = []
        for name in self.editable_fields:
            field = self.fields[name]
            assert field.scope in (Scope.content, Scope.settings)
            info = self._make_field_info(name, field)
            if info is not None:
                fields.append(info)
        fragment = Fragment(loader.render_django_template('public/lt_studio_edit.html', {'fields': fields}))
        fragment.add_javascript(loader.load_unicode('public/lt_studio_edit.js'))
        fragment.initialize_js('StudioEditableXBlockMixin')
        return fragment
