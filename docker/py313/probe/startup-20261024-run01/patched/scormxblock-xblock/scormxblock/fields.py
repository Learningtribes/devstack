from xblock.fields import DateTime as DefaultDateTime
from xblock.fields import String


class File(String):
    """LT file editor metadata; persisted values remain ordinary strings."""

    def __init__(self, *args, accept='*/*', extra_description='', **kwargs):
        super().__init__(*args, **kwargs)
        self.accept = accept
        self.extra_description = extra_description


class DateTime(DefaultDateTime):
    DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'

