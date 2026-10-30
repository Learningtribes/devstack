"""Run Django tests needing the legacy nose helper on Python 3.13.

The platform pins nose 1.3.7 for test utilities. Its path importer calls the
removed stdlib ``imp`` API, so provide those importer operations using
``importlib`` only for this test process; production/runtime imports are not
changed.
"""
import _imp
import importlib.machinery
import importlib.util
import os
import runpy
import secrets
import sys
import unittest
import unittest.runner


def find_module(name, path=None):
    spec = importlib.machinery.PathFinder.find_spec(name, path)
    if spec is None or spec.origin is None:
        raise ImportError("No module named {}".format(name))
    if spec.submodule_search_locations is not None:
        return None, spec.origin.rsplit(os.sep, 1)[0], ("", "", 5)
    suffix = next((s for s in importlib.machinery.all_suffixes()
                   if spec.origin.endswith(s)), ".py")
    return open(spec.origin, "rb"), spec.origin, (suffix, "rb", 1)


def load_module(name, file, filename, description):
    if description[2] == 5:
        init_file = os.path.join(filename, "__init__.py")
        spec = importlib.util.spec_from_file_location(
            name, init_file, submodule_search_locations=[filename]
        )
    else:
        spec = importlib.util.spec_from_file_location(name, filename)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load {} from {}".format(name, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


# ``nose.importer`` only needs these four historical names.
import types
imp_compat = types.ModuleType("imp")
imp_compat.find_module = find_module
imp_compat.load_module = load_module
imp_compat.acquire_lock = _imp.acquire_lock
imp_compat.release_lock = _imp.release_lock
sys.modules["imp"] = imp_compat
# nose 1.3.7 also imports a private unittest result name removed after 3.12.
if not hasattr(unittest.runner, "_TextTestResult"):
    unittest.runner._TextTestResult = unittest.runner.TextTestResult
if not hasattr(unittest, "_TextTestResult"):
    unittest._TextTestResult = unittest.runner.TextTestResult
os.environ.setdefault("EDXAPP_TEST_MONGO_HOST", "mongo")
os.environ.setdefault("EDXAPP_TEST_MONGO_PORT", "27017")
os.environ.setdefault("PY36_R1_MONGO_DB_PREFIX", "py313_scorm_test_" + secrets.token_hex(5))
import pymongo
_mongo_client = pymongo.MongoClient


def authenticated_test_mongo(*args, **kwargs):
    """Use the protected local test credentials for authenticated Mongo."""
    kwargs["username"] = kwargs.get("username") or os.environ.get("PY313_MONGO_USER", "edxapp")
    kwargs["password"] = kwargs.get("password") or os.environ["PY313_MONGO_PASSWORD"]
    kwargs["authSource"] = kwargs.get("authSource") or "admin"
    return _mongo_client(*args, **kwargs)


pymongo.MongoClient = authenticated_test_mongo
from pymongo.synchronous.cursor import Cursor
from pymongo.synchronous.collection import Collection


def legacy_cursor_count(self, with_limit_and_skip=False):
    """Restore the removed PyMongo Cursor.count used by legacy test stores."""
    query = dict(self._spec)
    if with_limit_and_skip and self._limit:
        query["$and"] = [query, {}]
        query["$and"][1]["_id"] = {"$exists": True}
    return self.collection.count_documents(query)


Cursor.count = legacy_cursor_count


def legacy_collection_update(self, selector, document, upsert=False, multi=False, **kwargs):
    """Compatibility for the legacy single-document Collection.update call."""
    result = (self.update_many(selector, document, upsert=upsert) if multi
              else self.update_one(selector, document, upsert=upsert))
    return {"n": result.matched_count + bool(result.upserted_id),
            "nModified": result.modified_count,
            "updatedExisting": result.matched_count > 0,
            "upserted": result.upserted_id}


Collection.update = legacy_collection_update


def legacy_collection_remove(self, selector, multi=True):
    """Compatibility for old modulestore calls on the registered test DB."""
    result = self.delete_many(selector) if multi else self.delete_one(selector)
    return {"n": result.deleted_count}


Collection.remove = legacy_collection_remove


# --- Keep PyMongo on real sockets while httpretty is active -------------------
# Why: 15 platform test modules (discussion_api, student/test_login,
# third_party_auth, ...) fake external HTTP services with httpretty. httpretty
# does this by replacing socket.socket and socket.getaddrinfo for the whole
# process while a test runs. Those tests also create courses, which talks to
# MongoDB. Under Python 2 the old PyMongo had already opened its connection
# before httpretty started. PyMongo 4 opens connections lazily and from
# background monitor threads, so they were created *inside* the httpretty
# window and got fake sockets: DNS was faked and socket timeouts were dropped.
# Server selection then waited forever and the full LMS run hung at about 27%
# (lms/djangoapps/discussion_api/tests/test_views.py).
# What: give PyMongo's connection modules a socket module whose socket and
# getaddrinfo are the real ones captured here, at process start, before any
# test can enable httpretty. Every other socket attribute is passed through.
# HTTP mocking is unchanged; only MongoDB traffic bypasses httpretty.
import socket as _real_socket_module

_REAL_SOCKET = _real_socket_module.socket
_REAL_GETADDRINFO = _real_socket_module.getaddrinfo


class _RealSocketModule(types.ModuleType):
    """socket module view for PyMongo that ignores httpretty's replacements."""

    socket = _REAL_SOCKET
    getaddrinfo = staticmethod(_REAL_GETADDRINFO)

    def __getattr__(self, name):
        return getattr(_real_socket_module, name)


import pymongo.pool_shared
import pymongo.synchronous.helpers
import pymongo.synchronous.pool

_pinned_socket = _RealSocketModule("socket")
for _module in (pymongo.pool_shared, pymongo.synchronous.helpers, pymongo.synchronous.pool):
    _module.socket = _pinned_socket

# --- Test-only package overlay ------------------------------------------------
# Why: the runtime lock does not ship test-only packages. /runtime/test-stubs
# holds the nose stub (nose.plugins.attrib.attr) that legacy tests import.
# factory_boy 3 moved DjangoModelFactory to factory.django; the legacy test
# factories still use factory.DjangoModelFactory, so alias the old name instead
# of editing hundreds of factory classes. Factory behaviour is unchanged.
sys.path.insert(0, "/runtime/test-stubs")
try:
    import factory
    import factory.django
    if not hasattr(factory, "DjangoModelFactory"):
        factory.DjangoModelFactory = factory.django.DjangoModelFactory
except ImportError:
    pass

# --- Command-line entry -------------------------------------------------------
# Why the __main__ guard: run_py313_pytest.py and the test-only sitecustomize.py
# (loaded by paver's pytest child process) import this module only to apply the
# shims above. Without the guard, that import would also start manage.py.
# Running this file directly behaves as before.
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in {"lms", "cms"}:
        raise SystemExit("usage: run_py313_legacy_tests.py lms|cms <manage.py arguments>")
    manage_args = sys.argv[1:]
    sys.argv = ["manage.py"] + manage_args
    platform_root = os.environ.get("PY313_PLATFORM_ROOT", "/edx/app/edxapp/edx-platform")
    os.chdir(platform_root)
    runpy.run_path("manage.py", run_name="__main__")
