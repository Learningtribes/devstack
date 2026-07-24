# py36-base.txt 补全分析

> Date: 2026-07-23
> base.txt: 200 PyPI 包 | py36-base.txt: 104 包 | 缺失: 128 | 真需补: ~85

## 已处理（20 个）

已在 py36-base.txt 中更名或升级：
mysql-python→mysqlclient, beautifulsoup→bs4, Django 1.11.15→1.11.29,
python-memcached 1.48→1.59, lxml 3.8→3.8 (keep), Pillow 3.4→8.4,
PyYAML 3.12→6.0.1, six 1.11→1.17, mako 1.0.2→1.1.6, markdown 2.6→3.3,
markupsafe 1.0→2.0, celery 3.1.25→3.1.25 (keep), kombu 3.0.37 (keep),
elasticsearch 1.9 (keep), redis 2.10.6 (keep), pymongo 2.9.1→3.9.0

## 不可装（5 个，Py2 专属）

py2neo==3.1.2, dm.xmlsec.binding==1.3.3, ipaddr==2.1.11, pygraphviz==1.1, pynliner==0.5.2

## Py2-only（4 个）

enum34, futures, python-openid, mysql-python — Python 2 才需要，3.6 自动跳过

## 需安装（~85 个）

```
analytics-python, argh, argparse, asn1crypto, attrs, babel, charade,
coreapi, coreschema, cssutils, django-appconf, django-auth-ldap,
django-babel, django-babel-underscore, django-braces, django-cors-headers,
django-countries, django-crequest, django-fernet-fields, django-filter,
django-ipware, django-memcached-hashring, django-method-override,
django-multi-email-field, django-mysql, django-oauth-toolkit,
django-object-actions, django-ratelimit, django-ratelimit-backend,
django-require, django-rest-swagger, django-ses, django-simple-history,
django-splash, django-statici18n, django-storages, django-tables2,
django-user-tasks, django-webpack-loader, djangorestframework-jwt,
djangorestframework-xml, docutils, dogapi, edx-ace,
edx-analytics-data-api-client, edx-ccx-keys, edx-celeryutils,
edx-completion, edx-django-oauth2-provider, edx-django-release-util,
edx-django-sites-extensions, edx-drf-extensions, edx-enterprise,
edx-milestones, edx-oauth2-provider, edx-organizations,
edx-rest-api-client, edx-user-state-client, edxval, event-tracking,
feedparser, firebase-token-generator, gunicorn, hash-ring, help-tokens,
ipaddress, isodate, itypes, jinja2, jsondiff, lepl, mailsnake, markey,
networkx, newrelic, nodeenv, openapi-codec, pathtools, paver, piexif,
pycountry, pycryptodomex, pygments, pyjwkest, pyjwt, pysrt,
python-levenshtein, python-saml, pyuca, reportlab, requests-oauthlib,
rest-condition, rfc6266-parser, rules, sailthru-client, semantic-version,
shortuuid, slumber, social-auth-app-django, social-auth-core,
sorl-thumbnail, tablib, unicodecsv, uritemplate, watchdog, wrapt,
xblock-review
```

## 已知风险

- `analytics` 有 Py2 反引号语法→需换 `analytics-python`（已列）
- `edx-enterprise` 依赖多，可能需额外装 edx-rest-api-client 等
- `python-saml` 依赖 dm.xmlsec（不可装）→跳过
- `lepl` 2012 年老包，可能无 wheel →跳过或替换
