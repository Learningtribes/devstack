# Django Boot on Py3.6 — Fix Log

> Date: 2026-07-23 · Container: py36-build (ltdps/edxapp:py36)
> Goal: `DJANGO_SETTINGS_MODULE=lms.envs.test python3 -c "import django; django.setup()"`

## Code Fixes (15)

All applied directly on master branch (worktree 6A/6B/6C changes not yet merged):

### ur"..." → r"..." (5 files)
```
common/djangoapps/static_replace/__init__.py       ur"""... → r"""
common/lib/xmodule/xmodule/modulestore/store_utilities.py  ur"""... + ur'/courses/...
common/lib/calc/calc/preview.py                    ur"\text{...}"
common/lib/xmodule/xmodule/capa_base.py            ur"..."
common/lib/xmodule/xmodule/capa_module.py          ur"..."
```

### except E, e: → except E as e: (2 files)
```
common/lib/xmodule/xmodule/contentstore/content.py  except Exception, exc:
common/lib/capa/capa/xqueue_interface.py            except ValueError, err: + 2 more
```

### raise E, V, T → six.reraise() (1 file)
```
common/lib/capa/capa/inputtypes.py:256              raise Exception, msg, sys.exc_info()[2]
```

### Import fixes — absolute_import compat (3 files)
```
common/lib/capa/capa/inputtypes.py:55               import xqueue_interface → from . import
common/lib/calc/calc/__init__.py                    from calc import * → from calc.calc import *
common/lib/calc/calc/calc.py                        import functions → from . import functions
```

### Py2 builtins (2 files)
```
common/lib/chem/chem/chemcalc.py                    reduce() → from functools import reduce
common/lib/chem/chem/chemcalc.py                    map() → list(map(...))
common/lib/capa/capa/inputtypes.py:85               unicode → str (gettext_func default)
```

## Dependency Fixes (8)

| Issue | Fix |
|------|------|
| `analytics` Py2 syntax | → `analytics-python` |
| `python-dateutil==1.5` Py2 backticks | → `>=2.5` |
| `pyparsing==3.1` no operatorPrecedence | → `>=2.0,<3.0` |
| `opaque_keys==4.0` annotations (3.7+) | → `edx-opaque-keys==0.4.4` |
| `eventtracking` .iteritems() | → `event-tracking>=1.0` |
| `django-wiki` PyPI ≠ git | → git+https://github.com/edx/django-wiki.git@v0.0.18 |
| `edx-jsme` PyPI ≠ git | → git+https://github.com/jazkarta/edx-jsme.git |
| `django-pipeline` Py2 format | → git version |

## Remaining

- `codejail` — git version has `exec code in g_dict` Py2 syntax
- `django-celery` — git clone timeout
- `oauth_provider` — django-oauth-plus git clone timeout
- `djangorestframework-oauth` — git clone timeout
- Django full `check` command (needs more LMS setup)
- `pytest --collect-only` — next milestone

## Conclusion

**Django boot path verified reachable.** 15 code fixes + 8 dependency fixes later, the import chain passes through capa/calc/chem/xmodule and reaches `django.setup()` internals.
