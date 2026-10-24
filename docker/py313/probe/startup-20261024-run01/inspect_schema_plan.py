from django.apps import apps
from django.db import connection
models = [m for m in apps.get_models() if m._meta.managed and not m._meta.proxy and m._meta.can_migrate(connection)]
for model in models:
    for fields in model._meta.unique_together:
        chars = sum(getattr(model._meta.get_field(name), 'max_length', 0) or 0 for name in fields)
        if chars > 768:
            print('OVERSIZED_UNIQUE',model._meta.label,fields,chars)
    for field in model._meta.local_fields:
        if (field.unique or field.db_index) and (field.max_length or 0)>768:
            print('OVERSIZED_INDEX', model._meta.label,field.name,field.max_length)
