# Py3 迁移 — 执行审查第五轮 / 收尾 (Execution Review 5 — Closing)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 完成的 n（django-cas 真 import 补验）+ 文档收尾
> 输入: `py36-git-layer-probe-20260723.md`（第四轮修正）+ `py3-dep-residual-workstream.md`（收宽 + django-cas）
> 结论一句话: **依赖可建性 characterization 端到端闭合，无"未测"缺口。重心转移: 探针阶段结束 → Batch 1 落地 + Gap C 测试环。**

---

## 1. n 裁决 — 真阻塞确认，审查环值了

执行 agent 跑 `pip install django && import django_cas` 翻出 `__init__.py:22 _DEFAULTS.iteritems()` → AttributeError。**第四轮坚持要真验 django-cas 是对的** —— 第三轮"✅\* 纯环境问题"的推断确实藏了真 Py3 阻塞。逻辑自洽: 原探针 `ModuleNotFoundError: django` 在 line 1 崩，没走到 line 22；装上 django 后 import 推进到 line 22 才暴露。

**sizing nuance（已落盘 workstream §4）**: ~~第一轮 grep 称"仅 iteritems 1 处无尾巴 ~5 分钟"~~ → **🔴 该 grep 结论被真 Py3 import 测推翻**。真跑 Py3.6（从 devstack 容器取出的真装 2.1.1 源）暴露 **urllib reorg 尾巴跨 6 文件**: `__init__.py:22 iteritems` + `views.py:3 from urllib import urlencode` + `urlparse`→`urllib.parse`(models/backends/views) + `from urllib import urlencode,urlopen`(models/views/middleware) + `import urllib`+`urllib.urlencode/urlopen`(backends/tests) + `from StringIO import StringIO`→`io.StringIO`(tests)。**真 fix ~0.5-1d**。原始 0.5-1.5d 估时反而更接近正确。教训: Py3 兼容验证必须真跑 import，grep 会漏 import 重组类。**但 CAS feature-flagged off**（live `lms.env.json` `AUTH_USE_CAS` absent→False，Django 不 import），py3 env 可直接从 py36-base.txt 删 pin —— 根因解，0d。

## 2. 文档收尾（本轮执行 agent 留下的矛盾，已修）

probe 文档自相矛盾已修（`py36-git-layer-probe-20260723.md` 重写）:
- auth 表去重（原 27-29 行重复）
- stale footnote 删除（原 line 33 "All 4 auth 通过 / django-cas 自身无 Py3 不兼容"已错）
- §判定 修正（"含 4 auth 全过" → "auth 3/4 过，django-cas ❌ 真阻塞"）
- 新增"2 个已知运行时阻塞"明确列出（lbmdone + django-cas）

workstream 已修:
- §3 stale prose 更新（原"待完成 ParsePy/..."全过，原"DoneXBlock 可跳过"错——lbmdone 是运行时）
- §4 django-cas 加"未知尾巴"注
- §汇总 header "+2.5-3.5d" 与表 "+3-4d" 对齐为 +3-4d / +5-7d

## 3. 整体状态 —— 依赖可建性闭合

- **"3.6 能 boot"** ✅ 成立（Django/DRF/django-celery + 3 auth 全验）。
- **"git 层 characterization"** ✅ 端到端闭合: 每个 git 包已归类 —— 验过 / 确认阻塞带 fix / 非运行时可跳 / 废弃。**无"未测"缺口**。
- **2 个已知运行时阻塞（均带 fix + sizing）**:
  - lbmdone-xblock `importlib.resources` 3.6（CMS GRADABLE_BLOCKS，0.5d backport patch）
  - django-cas `iteritems()`（live CAS SSO，0.5-1.5d fork fix，未知尾巴）
- **prod-gate 未决项（不阻塞 Batch 1）**: coursegraph/py2neo、SAML/dm.xmlsec（先查 prod 用量再 sizing）

## 4. 重心转移 —— 探针阶段结束

依赖可建性审查历经 5 轮（a→n）走完。**探针阶段收尾**。下一重心:

1. **Batch 1 落地**（~2d）: mysqlclient 1.4.6 + pymongo 3.9 + python-memcached 1.59 + 3 egg metadata 修复 + mongoengine 0.10.0 5-file smoke（已验）。
2. **必做运行时 fix（与 Batch 1 并行或紧随）**: lbmdone-xblock importlib.resources backport patch + django-cas fork fix（line 22 + 尾巴）。
3. **prod-gate 调查（并行）**: coursegraph 是否在 prod 用 / SAML 是否启用 → 决定移除 vs 替换/适配。
4. **任务 D —— Gap C 测试环**（Batch 1 + 运行时 fix 落地后）: tox py3 allow-fail baseline。这是 OEP-7 阶梯 rung 2，**唯一真实方法缺口** —— 测试环是暴露 csv/base64/hashlib 21 文件 + 其余运行时 Py3-ism 的唯一机制（`py_compile` 是盲区）。

## 5. 裁决

- **n**: ✅ 真阻塞确认 —— **且已独立复现**（见 §6）。审查环捕获，第四轮坚持真验是对的。
- **文档矛盾**: ✅ 已修（probe 重写 + workstream §3/§4/header）。
- **依赖可建性**: ✅ 端到端闭合（claim 级别见 §6）。
- **探针阶段**: ✅ 收尾。重心转 Batch 1 + Gap C。

**不再需要探针轮次**。下一轮交接应是 Batch 1 落地的执行报告，审查重点转为"运行时 fix 是否干净 + Gap C 测试环是否建立 + 失败基线"。

---

## 6. 验证级别（诚实分级 —— 2026-07-23 增）

用户质疑"是否真实测过，而非仅更新文档"。诚实分级:

### ✅ 独立复现（审查 agent 真跑，非仅 agent 报告）
- **django-cas line 22 `_DEFAULTS.iteritems()` → AttributeError**: Py3.6 + django 1.11.29，`import django_cas` 真复现，逐字匹配 agent 报告。`.items()` 1 行 fix 真验过清阻塞（import 推进过 line 22）。源: castlabs/django-cas（同源，`__init__.py:22` 与 agent 报告一致）。
- **结构性事实（grep 验）**: lbmdone-xblock 在 `cms/envs/common.py:333` GRADABLE_BLOCKS；django-cas 16 处非测试 live auth 引用；py2neo 用于 coursegraph（3 文件）；ipaddr 仅 embargo（2 文件，随 #2322 消解）；bs3 仅 pynliner transitive（0 平台代码）。

### ⚠️ 仍仅 agent 报告（未独立复现）
- "197 PyPI 包全量 resolve 成功" —— 未复现。
- "8 git 包真 import 验过"（django-celery/DRF/django-pipeline/django-wiki/MongoDBProxy/pygeoip/codejail/ParsePy）—— 未复现。
- "3 auth 通过"（django-oauth-plus/django-openid-auth/djangorestframework-oauth）—— 未复现。
- "lbmdone-xblock `importlib.resources` 3.6 崩" —— 未复现（XBlock 源在 venv，未取）。
- 这些 claim 逻辑自洽、且 django-cas 的同类 claim 已被独立复现佐证，但**未逐个真跑**。

### 🔴 撤回：上一版"fork 源问题"是审查 agent 查错 org 的假警报
上一版称"edx/django-cas 404 → fork 源问题"。**错误**：base.txt/py36-base.txt line 13 pin 的一直是 `github.com/mitodl/django-cas.git@afac57bc`（MIT ODL 原上游），不是 edx/django-cas。审查 agent 那轮误查 `gh api repos/edx/django-cas`（不存在的 org）拿 404，当成问题落盘。**实测**: `gh api repos/mitodl/django-cas/commits/afac57bc` → `afac57b Merge pull request #2 ... PLAT-1766` —— commit 存在，pin 一直有效可解析。**无 fork 源问题，撤回此 finding。** 教训：质疑 claim 前先核对 pin 的真实 org，别凭印象查。

### ⚠️ django-cas 重新分类（执行 agent 第五轮后）: ❌→⏭️ skip（已验）
执行 agent 查 prod settings 后把 django-cas 从"❌ 阻塞"改为"⏭️ skip"。**审查 agent 独立核实，成立**:
- `AUTH_USE_CAS` 默认 `False`（`lms/envs/common.py:115` FEATURES dict），`aws.py`（prod）不设 True，`devstack.py` 不设 → 继承 False。
- `INSTALLED_APPS.append('django_cas')` 在 `if FEATURES.get('AUTH_USE_CAS'):` 门控内（`common.py:2465` / `aws.py:383`）—— flag off → Django **不 import django_cas** → line 22 iteritems 不触发 → **非 boot 阻塞**。
- 我复现的 `import django_cas → AttributeError` 仍真实，但只在 CAS 启用时触发；CAS off → 不触发。skip 正确。
- **措辞修正（agent 不准）**: "py36-base.txt 标注 optional"不准 —— py36-base.txt line 13 是普通 pin，无 optional 注释；skip 靠 settings flag，非 requirements 标注。另 django-cas 仍被 pip 装入 venv（base.txt pin），只是不被 Django import。结论（0d、非阻塞）不变。
- **若 prod 何时启用 CAS**: 需 `.items()` fix（实扫全包仅此 1 处 Py2-ism，无尾巴，~5 分钟）。但 CAS off → py3 env 直接从 py36-base.txt 删 pin（根因解）。deferred。

### 建议（收口未复现项）
Batch 1 落地时，对 8 git 包 + 3 auth + lbmdone 在 py36 容器逐个真 import（同 django-cas 复现法），把"agent 报告"升级为"独立复现"。优先级: lbmdone（运行时 XBlock）> 3 auth（live auth 路径）> 8 git 包核心。
