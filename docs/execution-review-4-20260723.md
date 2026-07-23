# Py3 迁移 — 执行审查第四轮 (Execution Review 4)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 完成的 j-m（8 git 包补测 + lbmdone 运行时核验 + coursegraph prod gate + 估时收宽）
> 输入: `py36-git-layer-probe-20260723.md`（第三轮修正）+ `py3-dep-residual-workstream.md`（收宽）+ 代码级 grep 验证（GRADABLE_BLOCKS、django-cas 实际用量）
> 结论一句话: **接近闭合。3 auth 可靠，django-cas partial 未真验（唯一未闭合项，~10 分钟补验）。lbmdone 运行时阻塞已确认 + sizing。可进 Batch 1。**

---

## 1. 4 auth 通过判定 — 3 可靠，django-cas 是 partial

- django-oauth-plus / django-openid-auth / djangorestframework-oauth —— 真完整 import，✅ 可靠。
- **django-cas partial，非"通过"**: 探针自写 `ModuleNotFoundError: django`，结论"纯环境问题自身无 Py3 不兼容"是**推断非验证**。`ModuleNotFoundError: django` 只证明 django-cas 模块**解析并执行到第一行 `import django`**，它**自己的代码（views/backends/middleware）的 Py3 运行时行为完全未验**。
- **django-cas 是 live auth 路径**（grep 16 处非测试引用）: `lms/urls.py` cas-auth/logout 路由；`lms/envs/aws.py` + `common.py` 的 INSTALLED_APPS/AUTH_BACKENDS/MIDDLEWARE（feature-flag 下 CAS SSO）；`external_auth/views.py` login。**prod 若用 CAS SSO，django-cas 的 Py3 兼容就重要** —— 不能停在"推断 OK"。
- **补验（~10 分钟）**: `pip install django==1.11.29 && python -c "import django_cas.views, django_cas.backends, django_cas.middleware"` —— exercise platform 用的三个子模块。探针"✅\*"应降为"⚠️ partial 待补验"。

## 2. lbmdone-xblock 运行时阻塞 — 确认真实，方案合理

- **确认在 GRADABLE_BLOCKS**: `platform/cms/envs/common.py:333` GRADABLE_BLOCKS 列表含 `'lbmdonexblock'`，另在 cms:1396 + lms:3395。运行时 XBlock，非纯测试。✅ k 判定对。
- importlib.resources 是 3.7+ stdlib，3.6 无。XBlock 源在 venv（非仓库内），无法从 platform/ 直接验那行 import，但运行时存在性已坐实。
- **方案合理**: lbmdone 是 Learningtribes fork（egg `lbmdone-xblock`），可 patch —— 装 `importlib_resources` backport + 改 XBlock `import importlib.resources` 为 try/except，或升版本。0.5d 对 vendored fork patch 合理。
- acid-xblock 不在 settings → 跳过 ✅。
- 残留覆盖 gap（可接受）: 探针靠 settings-grep 抓 XBlock；经课程内容加载但不在 settings 的 XBlock 未覆盖。GRADABLE_BLOCKS + entry points 覆盖 runtime-relevant 的，acceptable。

## 3. 估时 2-3d / 4-6d — 合理

m 收宽到位。best-case +2-3d（4 auth 全过 + SAML 不用 + coursegraph 移除）、现实 +4-6d（coursegraph 替换 + SAML 在用）—— 诚实 bracket。item 3 lbmdone 0.5d、item 4 git 层 0.5d 合理。coursegraph 1-3d / SAML 0-2d 带 prod gate，结构与估时一致。

---

## 4. j-m 完成度裁决

| 任务 | 状态 | 裁决 |
|:---:|---|---|
| j | 8 git 包补测 | ⚠️ 3 auth 可靠，django-cas partial 未真验（live CAS SSO 路径）|
| k | lbmdone 运行时核验 | ✅ GRADABLE_BLOCKS 确认 + 方案合理；acid 跳过 ✅ |
| l | coursegraph prod gate | ✅ 已加，与 SAML 同纪律 |
| m | 估时收宽 | ✅ 2-3d/4-6d honest bracket |

---

## 5. 整体状态

- **"3.6 能 boot"** ✅ 成立（Django/DRF/django-celery + 3 auth 全验）。
- **"git 层核心可建"** ✅ 成立（仅 lbmdone-xblock 一个已知运行时阻塞，已 sizing 0.5d）。
- **唯一未闭合**: django-cas 真 import 验证（10 分钟补验）。
- **可进 Batch 1**: scoped Batch 1（~2d: mysqlclient + pymongo 3.9 + memcached + egg 修复 + mongoengine smoke 已验）+ 残留工作流（lbmdone 0.5d 必做 + coursegraph/SAML prod-gate 后定）。

---

## 6. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第四轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-4-20260723.md
—— 先读 §5 整体状态。

裁决速览:
- 接近闭合。"3.6 能 boot" + "git 层核心可建" ✅ 成立。
- j-m ✅ 完成，唯一未闭合: django-cas 是 partial 验证（ModuleNotFoundError: django，未真 exercise 自己的代码），且它是 live CAS SSO 路径。
- lbmdone-xblock 运行时阻塞已确认 + sizing 0.5d。

这一轮只剩 1 件补验 + 即可进 Batch 1:

n. django-cas 真 import 补验（~10 分钟）:
   pip install django==1.11.29
   python -c "import django_cas.views, django_cas.backends, django_cas.middleware"
   三个子模块（platform 实际用的: urls.py 的 views、aws.py 的 backends+middleware）全 import 成功 → django-cas ✅ 真验过，标进 py36-git-layer-probe 的 auth 表（✅\* → ✅）。
   若任一子模块 import 崩 → 是真 Py3 阻塞，进残留工作流 §（CAS auth 适配）。

做完 n（且通过）→ 进 Batch 1 落地:
   scoped Batch 1（~2d）: mysqlclient 1.4.6 + pymongo 3.9 + python-memcached 1.59 + 3 个 egg metadata 修复（edx-ora2→#egg=ora2, xblock-done→#egg=lbmdone-xblock, edx-sga 待核实）+ mongoengine 0.10.0 5-file smoke（已验）。
   + 残留工作流必做: lbmdone-xblock importlib.resources backport patch（0.5d，CMS GRADABLE_BLOCKS 运行时，不可跳）。
   + prod-gate 后定: coursegraph/py2neo（先查 prod 用量）、SAML/dm.xmlsec（先查 prod 是否用 SAML）。
→ Batch 1 + lbmdone patch 落地后 → 任务 D（tox py3 allow-fail baseline，攻 Gap C —— 唯一真实方法缺口）。

并行: #2348 推 review approval（仍 REVIEW_REQUIRED）；DCC #2322/#2323/#2324 APPROVED 可 merge（#2322 merge 顺带消解 ipaddr）。

硬约束（不变，见 review-verdict §5）: 共享 DB 安全（Py3 首次 migrate 前独立 DB 名或 lock）/ mongoengine 0.10.0 + pymongo 3.9 为准 / 迁移修专用分支、migrations 不内联 removal 分支 / diff 数字自跑 git 验证别照搬。

回报格式: 「做了什么 / 实测命令+输出 / 判定 / 下一步」。先做 n（django-cas 真验）—— 它是 git 层 auth 最后一道，过了就整体闭合进 Batch 1。
```
