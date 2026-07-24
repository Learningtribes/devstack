## Py3.6 Django Boot + Check — MILESTONE

### Status: `System check identified no issues (0 silenced).`

```
Django 1.11.29 + Python 3.6.15
django.setup() ✅
call_command("check") ✅
```

### Container: py36-build (ltdps/edxapp:py36)

- Django 1.11.29 locked via pip constraint (6 bridge pins)
- celery 3.1.25, kombu 3.0.37, pymongo 3.9.0, mongoengine 0.10.0, mysqlclient 1.4.6
- `kombu.async` OK (async = soft keyword on 3.6)
- ~60+ code fixes applied to get to this point
- Fixes committed to `py36-boot-fixes` branch (pushed to origin)

### Fix categories

| Type | Count | Examples |
|------|:---:|------|
| ur"..." → r"..." | 6 | static_replace, store_utilities, calc/preview, capa_base/module |
| except E, e: → as e: | 15+ | contentstore, xqueue_interface, graders, oauth_provider, wiki, pysrt |
| raise E, V, T → reraise | 8 | capa_base/module, html_module, xml_module, graders, inputtypes |
| cStringIO → six.moves | 13 | util/models, course_module, git_import |
| urlparse → six.moves | 10+ | annotator_mixin, course_overviews, credentials, programs, helpers, login |
| import fixes | 8 | comment_client, calc/calc, grades, xqueue_interface, user_api |
| Py2 builtins | 5 | long→int, reduce, map, unicode, string.letters |
| codejail | 3 | exec code in g_dict → exec(code, g_dict), 0775→0o775 |
| Third-party patches | 10+ | oauth_provider, wiki, pysrt, provider, edx_when, social_auth, enterprise |
| base_name→basename | 3 | DRF register() API |
| force_unicode→force_text | 2 | Django 1.11 deprecation |
| hashlib encode | 1 | edxmako/paths.py |

### Known stubs (deferred, prod-gate pending)

- coursegraph: py2neo → None
- SAML: onelogin stub
- openassessment: empty stub package (ORA2 git clone timeout)
- enterprise: EdxRestApiClient → None
- edx_rest_framework_extensions: JwtAuthentication → None

### Next steps

1. `pytest --collect-only` — verify test collection works
2. Tox py3 allow-fail baseline (Gap C)
3. Commit remaining fixes to py36-boot-fixes
4. py36-base.txt full generation from base.txt
