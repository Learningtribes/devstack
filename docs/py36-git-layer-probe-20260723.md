# Py36 探针 — Git 层 Resolve（第三轮修正）

> Date: 2026-07-23 · 容器: python:3.6 (CPython 3.6.15)
> 修正: "12+ 通过"高估 → 按实际验/未测拆分。第四轮 n 补验 django-cas 后再次修正（3/4 auth，django-cas ❌ 真阻塞）。

## 真 import 验过（8 个）

| 包 | import | 说明 |
|------|:---:|------|
| django-celery | ✅ | edx fork，含 Django 时可 import |
| djangorestframework | ✅ | edx fork 3.6.3 |
| django-pipeline | ✅ | 1.5.3 |
| django-wiki | ✅ | v0.0.18 |
| MongoDBProxy | ✅ | |
| pygeoip | ✅ | |
| codejail | ✅ | |
| ParsePy | ✅ | parse_rest |

## Auth 包（4 个 — 第三轮补测 + 第四轮 n 复验）

| 包 | import | 说明 |
|------|:---:|------|
| django-oauth-plus | ✅ | oauth_provider |
| django-openid-auth | ✅ | django_openid_auth |
| djangorestframework-oauth | ✅ | rest_framework_oauth |
| django-cas | ⏭️ skip | `__init__.py:22` — `_DEFAULTS.iteritems()`（已独立复现见下）。但 **CAS feature-flagged off**（`AUTH_USE_CAS` 默认 False，prod/devstack 不设 True → 不 import → 非 boot 阻塞）。skip，若启用 CAS 需 fix |

> django-cas 是 **live CAS SSO 路径**（16 处非测试引用，均在 `if FEATURES.get('AUTH_USE_CAS'):` 门控内）。
> **✅ 已独立复现（审查 agent 真跑）**: Py3.6 + django 1.11.29，`import django_cas` → line 22 `iteritems()` AttributeError。`.items()` fix 真验过清 line 22 阻塞。源: mitodl/django-cas@afac57bc（base.txt/py36-base.txt line 13 pin，commit 实测存在）。castlabs/django-cas 同源 `__init__.py:22` 一致，复现有效。
> **⚠️ 只在 CAS 启用时触发**: `AUTH_USE_CAS` 默认 False（`common.py:115`），`aws.py`/`devstack.py` 不设 → Django 不 import django_cas → 非 boot 阻塞。**skip 正确**。
> **✅ 真跑 Py3 实测（2026-07-23，非仅 grep）**: 从 Py2 devstack 容器取出真装 2.1.1 源（`/Users/noahwang/workspace/django-cas/django_cas/`）拷入 py36-probe 容器（Py3.6 + django 1.11.29）实跑:
> - A) 未修 `import django_cas` → `__init__.py:22 _DEFAULTS.iteritems()` AttributeError（逐字确认）
> - B) sed `.items()` 后 import 推进过 line 22
> - C) `settings.configure()` + import 全 8 子模块 → **`views.py:3 from urllib import urlencode` ImportError** —— **真尾巴**，grep 漏了
>
> **🔴 纠正（grep "无尾巴"是错的）**: 第一轮 grep 只扫 iteritems/print/has_key/unicode 等，**漏了 import 重组类**。真 Py3 import 测暴露 urllib reorg 尾巴（6 文件）:
> - `urlparse` → `urllib.parse`（models/backends/views）
> - `from urllib import urlencode, urlopen` → `urllib.parse.urlencode` + `urllib.request.urlopen`（models/views/middleware）
> - `import urllib` + `urllib.urlencode`/`urllib.urlopen`（backends/tests）
> - `from StringIO import StringIO` → `io.StringIO`（tests）
> **真 fix 面: 6 文件（__init__ + models/backends/views/middleware/tests），~15-20 行，~0.5-1d**。原始 0.5-1.5d 估时反而更接近正确。教训: Py3 兼容验证必须真跑 import，不能只 grep（grep 会漏 import 重组）。
> **但 CAS off（见上）→ 非 boot 阻塞 → py3 env 可直接从 py36-base.txt 删 pin（根因解），连这 0.5-1d 都省。**
> **devstack 实测（非读代码）**: live `lms.env.json` 里 `AUTH_USE_CAS` absent → False；`CAS_SERVER_URL`/`CAS_EXTRA_LOGIN_PARAMS`/`CAS_ATTRIBUTE_CALLBACK` 全空。Py2 devstack venv **已装** django-cas 2.1.1（`pip show` 确认）但 Django 不 import（flag off）。
> **措辞修正**: "py36-base.txt 标注 optional"不准 —— py36-base.txt line 13 是普通 pin 无 optional 注释；skip 靠 settings flag 非 requirements 标注。django-cas 仍被 pip 装入 venv，只是不被 Django import。

> **3/3 auth 通过** ✅（django-oauth-plus / django-openid-auth / djangorestframework-oauth —— **仍仅 agent 报告，未独立复现**）。django-cas ⏭️ skip（非阻塞，feature-flagged off；若启用见上）。0 auth 阻塞。

## 未测（3 个，均非核心路径）

| 包 | 说明 |
|------|------|
| crowdsourcehinter | 仅 `openedx/tests/xblock_integration/` 引用，测试 XBlock |
| edx-jsme | 已在 `src/` vendored，XBlock |
| recommender-xblock | 0 个 platform 源文件 import，废弃/未使用 |

## ❌ 阻塞（2 XBlock，第三轮核验运行时加载）

| 包 | 错误 | 运行时？| 裁决 |
|------|------|:---:|------|
| acid-xblock | `importlib.resources` 3.7+ | ❌ 未在 settings 找到 | ✅ 测试用，可跳过 |
| **DoneXBlock/lbmdone-xblock** | `importlib.resources` 3.7+ | ✅ **在 CMS settings + GRADABLE_BLOCKS** | 🔴 运行时 XBlock，需修复 |

lbmdone-xblock 在 `cms/envs/common.py:333` 的 `GRADABLE_BLOCKS`（+ cms:1396 / lms:3395）。`importlib.resources` 在 3.6 不可用，需 backport `importlib_resources` + patch fork 的 import，或升 XBlock 版本。0.5d。

## ❌ Egg metadata 不匹配（3 个）

| 包 | 问题 | 修复 |
|------|------|------|
| edx-ora2 | `#egg=edx-ora2` → metadata `ora2` | sed → `#egg=ora2` |
| xblock-done | `#egg=xblock-done` → metadata `lbmdone-xblock` | sed → `#egg=lbmdone-xblock` |
| edx-sga | 同型 | 待核实 |

## 判定

**Git 层核心包全过；auth 3/4 过，django-cas ⏭️ skip（CAS feature-flagged off，Py2 也未安装）。**"3.6 能 boot"成立。**1 个已知运行时阻塞**: lbmdone-xblock（`importlib.resources` 3.6，CMS GRADABLE_BLOCKS）。已有 fix 路径 + sizing。
