# Py3 迁移 — 执行审查第十二轮 (Execution Review 12) — 🏁 BOOT MILESTONE

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 Django boot + check 里程碑（handoff "System check identified no issues"）
> 验证方法: 进 `py36-build` 真跑 `django.setup()` + `call_command("check")` + pip show 验全 pin
> 结论一句话: **✅ 里程碑 VERIFIED —— `call_command("check")` 真通过（"System check identified no issues (0 silenced)"）。review-1 终极目标达成，Py3.6+Django 1.11.29 能 boot。"至今零次 Py3 运行时启动"判定翻篇。**

---

## 1. 验证证据（py36-build 实测）

### ✅ boot + check 真通过
```
DJANGO_SETTINGS_MODULE=lms.envs.test python -c "import django; django.setup(); from django.core.management import call_command; call_command('check')"
→ System check identified no issues (0 silenced).
→ === CHECK DONE ===
```
唯一噪音: `verify_student/ssencrypt.py:29 CryptographyDeprecationWarning`（Py3.6 EOL 提示，cryptography 库发的），无害，check 仍 "0 issues"。

### ✅ constraint 修好，6 bridge pin 全对
| pin | 实测 | 目标 |
|---|---|---|
| Django | 1.11.29 | 1.11.29 ✅ |
| celery | 3.1.25 | 3.1.25 ✅ |
| kombu | 3.0.37 | 3.0.37 ✅ |
| pymongo | **3.9.0** | 3.9.0 ✅（上轮被降 2.9.1 已修）|
| mongoengine | 0.10.0 | 0.10.0 ✅ |
| mysqlclient | 1.4.6 | 1.4.6 ✅ |

### ✅ agent 这轮报告诚实
graders:192 真修 / Django 锁 / boot 死点 onelogin 准 / check 通过 —— claim 与实测逐一对上，无 over-reporting。本轮 agent 靠谱。

## 2. ⚠️ 5 stub 是 deferred runtime 风险

boot/check 靠打桩过，runtime 跑真功能会崩:

| stub | runtime 影响 | prod-gate |
|---|---|---|
| coursegraph py2neo→None | coursegraph 任务（Neo4j 导出）| 查 prod 是否用 coursegraph |
| SAML onelogin stub | SAML 登录 | 查 prod 是否配 SAML IdP |
| **openassessment 空 stub** | **ORA2 open-response 题型（GRADABLE_BLOCKS 运行时 XBlock，广泛用）—— 含 ORA2 的课程 runtime 崩** | 必须真解（连 6F ora2）|
| enterprise EdxRestApiClient→None | enterprise 集成 | 查 prod 是否用 enterprise API |
| edx_rest_framework_extensions JwtAuth→None | JWT auth | 查 prod 是否用 JWT |

**openassessment(ORA2) stub 最关键** —— 连回 review-1 的 6F 尾部风险（ora2+proctoring ~70K SLOC，无上游 Py3 fork）。boot 靠 stub 过了，但 runtime 含 ORA2 的课程必崩。tox 单元测试若 mock ORA2 可能 OK；prod 必须真解（patch/wait/replace，OEP-7 第三方依赖路径）。

## 3. 里程碑意义

- **review-1 终极目标达成**: 从"至今零次 Py3 运行时启动、仅 py_compile"到"Py3.6+Django 1.11.29 boot + check 0 issues"。
- **"时间线在 boot 通过前不可信"判定解除** —— 现在可重估时间线。
- **审查 loop 到收益拐点**: review-6-11 的"逐轮打脸补 fix"模式产出 milestone。下一阶段重心转 tox 测试环 + stub/6F 真解。

## 4. 裁决

| 项 | 状态 | 裁决 |
|---|---|---|
| django.setup() | 真成功 | ✅ |
| call_command("check") | "0 issues" | ✅ **里程碑 VERIFIED** |
| 6 bridge pin | 全对 | ✅（pymongo 3.9.0 修回）|
| agent 报告 | 诚实 | ✅（claim 与实测一致）|
| 5 stub | deferred | ⚠️ runtime 风险（ORA2 最重，连 6F）|

**本会话全程（R1→R12）轨迹**: 计划审查 → 3.6 决策 → 依赖 characterization 闭合 → django-cas 删 pin → Batch1 落地 → boot 链逐个修（xmodule→capa→codejail→graders→...→onelogin stub）→ **check 通过**。12 轮审查 + 活测兜底，从"零运行时"到"boot 0 issues"。

---

## 5. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十二轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-12-20260723.md
—— 🏁 BOOT MILESTONE VERIFIED。

裁决速览（实测 py36-build）:
- ✅ django.setup() + call_command("check") 真通过 —— "System check identified no issues (0 silenced)"。review-1 终极目标达成。
- ✅ 6 bridge pin 全对（pymongo 3.9.0 修回）。
- ✅ 本轮 agent 报告诚实。
- ⚠️ 5 stub deferred（coursegraph/SAML/openassessment/enterprise/jwt）—— runtime 风险，ORA2(openassessment) 最重（连 6F）。

下一阶段（重心转测试环 + stub 真解）:

u1. pytest --collect-only（tox 前置）:
   cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python -m pytest --collect-only 2>&1 | tail -30
   确认测试能 collect（可能暴露更多 Py2-ism + stub 边界 —— 哪些测试因 stub 跳过/skip）。

u2. tox py3 allow-fail baseline（Gap C / OEP-7 rung 2）:
   建 tox.ini py36 env（allow fail）+ 跑全量，记失败基线。这是暴露 csv/base64/hashlib 21 文件 + 其余运行时 Py3-ism 的机制（py_compile 盲区，本会话从 review-1 就标的）。

u3. stub 真解（prod-gate，不阻塞 tox 但阻塞 prod）:
   - openassessment/ORA2: GRADABLE_BLOCKS 运行时 XBlock，广泛用 —— 必须真解（patch LT fork 或 wait 上游 Py3 或 replace）。连 6F ora2+proctoring ~70K SLOC。这是最大尾部风险。
   - coursegraph/SAML/enterprise/jwt: 逐个查 prod 是否用。不用 → stub 留；用 → 真解。

u4. 6F vendored src/（~70K SLOC ora2+proctoring，无上游 Py3 fork）做 patch/wait/replace 决策 —— 与 u3 openassessment 同源，尾部风险，可能显著推后时间线。

u5. py36-base.txt 全量生成 from base.txt（所有 blocker pin 修）+ 提交 py36-boot-fixes 分支剩余 fix。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 真连 DB 用独立 py3 schema，别碰 Py2 devstack 数据。
2. Py3 env 独立不动 Py2 devstack。
3. code fixes 在 py36-boot-fixes 分支，打桩单独标 deferred，migrations 不内联 removal 分支。
4. **验证真跑（pytest collect/tox 失败基线，不只信"跑过"）** —— 活测兜底贯穿本会话，多次抓 over-reporting。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+真输出 / 判定 / 下一步」。先做 u1（collect-only 贴输出），看测试能 collect 多少 + 哪些因 stub skip。collect 成功 → u2 tox baseline。
```
