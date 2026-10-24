"""Verify the genuine File service provider and persisted local storage."""
from importlib.metadata import distributions

from djpyfs import djpyfs
from djpyfs.models import FSExpirations
from xblock.reference.plugins import djpyfs as plugin

owners = [
    distribution.metadata["Name"] for distribution in distributions()
    if any(str(file) == "djpyfs/djpyfs.py" for file in (distribution.files or []))
]
assert owners == ["openedx-django-pyfs"], owners
assert plugin
with djpyfs.get_filesystem("run30-storage-regression") as filesystem:
    filesystem.writetext("real-storage.txt", "Python3.13 real File storage")
    assert filesystem.readtext("real-storage.txt") == "Python3.13 real File storage"
    filesystem.writebytes("real-storage.bin", b"\x00\xffPython3.13")
    assert filesystem.readbytes("real-storage.bin") == b"\x00\xffPython3.13"
    filesystem.expire("real-storage.txt", 0, expires=False)
    record = FSExpirations.objects.get(
        module="run30-storage-regression", filename="real-storage.txt"
    )
    assert record.expires is False
    print("PASS unique provider", owners, "text/bytes/expiration", filesystem.get_url("real-storage.txt"))
