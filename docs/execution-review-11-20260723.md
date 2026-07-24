# Py3 迁移 — 执行审查第十一轮 (Execution Review 11)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 s1（graders:192 真修 + Django constraint + 3 batch fixes）
> 验证方法: 进 `py36-build` 真跑 sed + Django 版本 + django.setup() + 查 constraint 文件 + SAML 门控
> 结论一句话: **agent 这轮报告诚实（graders 真修、Django 锁 1.11.29、boot 死点 onelogin 准）。但 constraint 不全 → pymongo 被悄悄降回 2.9.1；SAML onelogin import 无门控 + TPA 启用 → boot 必 stub/装。**

---

## 1. 验证证据（py36-build 实测）

### ✅ agent 这轮报告诚实（与实测一致）
- **graders:192 真修了**: `sed -n 192p` → `six.reraise(ValueError, ValueError(msg), sys.exc_info()[2])`（不再是 Py2 raise，上轮假 claim 这轮真修）
- **Django 锁 1.11.29**: `import django; django.VERSION` → `(1, 11, 29, 'final', 0)`（非 3.2，constraint 生效）
- **boot 死点准**: `third_party_auth/saml.py:12 from onelogin.saml2.settings import OneLogin_Saml2_Settings → ModuleNotFoundError: No module named 'onelogin'`，与 agent 报告一致
- 3 batch fixes（raise E,V,T xmodule / cStringIO 全树 / unicode capa）应用，boot 链推进到 apps.populate() 的 third_party_auth

**agent 报告质量提升** —— 本轮无 over-reporting，claim 与实测逐一对上。

### ❌ constraint 文件不完整 —— pymongo 被悄悄降回 2.9.1
constraint 只锁 `Django==1.11.29`。实测其他 pin:
| pin | 实测 | 目标 | 裁决 |
|---|---|---|---|
| celery | 3.1.25 | 3.1.25 | ✅ |
| kombu | 3.0.37 | 3.0.37 | ✅ |
| mysqlclient | 1.4.6 | 1.4.6 | ✅ |
| mongoengine | 0.10.0 | 0.10.0 | ✅ |
| **pymongo** | **2.9.1** | **3.9.0** | **❌ 被降回 Py2-prod 版** |

`pymongo 2.9.1` 是 Py2-prod pin，被某 transitive dep 拉回（constraint 没锁它）。Py3.6 上或能 import 但非目标版 + 可能 runtime 问题。**正是 review-focus #1 担的 silent-upgrade/downgrade 风险，已实测坐实。**

### SAML onelogin —— import 非门控 + TPA 启用
- live `lms.env.json` `ENABLE_THIRD_PARTY_AUTH: true` → third_party_auth 在 INSTALLED_APPS → models 加载 → saml.py 加载
- `third_party_auth/saml.py:12` `from onelogin.saml2.settings import OneLogin_Saml2_Settings` —— **顶层无条件 import**，无 `if` 门控
- → 不管 prod 是否配 SAML provider，**boot 时这个 import 必发生**。必须让 onelogin 可 import（stub 假模块 或 装 python3-saml）

## 2. review focus 回答

### (1) Django constraint 对? 其他包悄悄升级风险?
方式对（pip constraint 防 Django→3.2）但**不完整**。pymongo 已被降回 2.9.1（实测坐实）。constraint 必须锁全部 bridge pin:
```
Django==1.11.29
celery==3.1.25
kombu==3.0.37
pymongo==3.9.0
mysqlclient==1.4.6
mongoengine==0.10.0
```
（以及任何其他怕被 transitive 改的 pin）。约束只 Django = 漏网。

### (2) 30+ fixes 提交 py36-boot-fixes 分支?
是，开分支（CLAUDE.md: master 上先开分支）。但**分开**:
- 真修（ur/except/raise/cStringIO/long/import/exec）→ commit 为 `py36-boot-fixes`
- **打桩的（coursegraph py2neo=None、SAML onelogin stub）单独标 `deferred`**，别混进"fix"（它们是 import 通过但 runtime 坏）

### (3) SAML onelogin stub 可接受?
- **boot 阶段: 是** —— stub `onelogin.saml2.settings`（假模块让 import 过）。onelogin import 无门控（saml.py 顶层），无法靠 flag 跳。
- **runtime SAML 登录: 看 prod-gate** —— 查 prod 是否真配 SAML IdP provider（不只 ENABLE_THIRD_PARTY_AUTH，是实际 SAML provider config）。不用 → stub 留；用 → 装 python3-saml（真 onelogin）+ dm.xmlsec 一并解（1-2d）。

### (4) 下一步
扩 constraint 全 pin → stub onelogin 让 boot 过 → 清剩余 ~10 apps.populate 阻塞 → `call_command("check")` → `pytest --collect-only` → tox baseline。prod SAML gate + coursegraph gate 并行。

## 3. 裁决

| 项 | 状态 | 裁决 |
|---|---|---|
| graders:192 fix | 真修 | ✅（上轮假，这轮真，sed 验）|
| Django constraint | 锁 1.11.29 | ✅ 方式对 |
| constraint 完整性 | 只锁 Django | ❌ pymongo 降回 2.9.1（silent downgrade 实测坐实）|
| 3 batch fixes | 应用 | ✅ boot 推进到 third_party_auth |
| boot 死点 | onelogin | ✅ 报告准，agent 这轮诚实 |
| coursegraph/saml stubs | deferred | ⚠️ import 过 runtime 坏，prod-gate 待验 |

**进展实质**: graders 修 + Django 锁 + 3 batch fix 让 boot 从 review-10 的 graders 死点推进到 apps.populate() 的 third_party_auth/saml。离 setup 成功又近一步（~10 阻塞）。

**agent 报告质量**: 本轮诚实（与实测逐一对上）。但仍需活测兜底 —— pymongo silent downgrade 就是只读 fix 表看不出的。

---

## 4. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十一轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-11-20260723.md
—— 先读 §1（pymongo silent downgrade）+ §2（constraint 全 pin / SAML stub）。

裁决速览（实测 py36-build）:
- ✅ 这轮报告诚实: graders:192 真修、Django 锁 1.11.29、boot 死点 onelogin 准。
- ❌ constraint 不全 —— pymongo 被悄悄降回 2.9.1（实测），需锁全部 bridge pin。
- SAML onelogin import 无门控 + ENABLE_THIRD_PARTY_AUTH=true → boot 必 stub/装 onelogin。

你这轮补做:

t1. **扩 constraint 锁全部 bridge pin**（防 silent downgrade，pymongo 已中招）:
   /root/.pip/constraints.txt 加:
     Django==1.11.29
     celery==3.1.25
     kombu==3.0.37
     pymongo==3.9.0
     mysqlclient==1.4.6
     mongoengine==0.10.0
   然后 pip install -U pymongo==3.9.0 强制回 3.9.0，pip show 验全 pin 到位。

t2. **stub onelogin 让 boot 过**（boot 阶段，runtime 看 t5）:
   third_party_auth/saml.py:12 顶层无条件 import onelogin，无法靠 flag 跳。
   创建假模块 site-packages/onelogin/saml2/settings.py 提供 OneLogin_Saml2_Settings 空壳类（+ saml.py 其他用到的 onelogin 名字）。
   或装 python3-saml（若 Py3.6 兼容 + 包含 onelogin.saml2）—— 优先尝试，装不上再 stub。
   stub 后重跑 setup，贴 traceback 看下一个阻塞。

t3. **逐个清剩余 ~10 apps.populate 阻塞**: 每个同模式（import 无门控 + Py2-ism 或缺包）。每修一个重跑 setup 贴真输出，直到 `django.setup()` 真成功（print "SETUP OK"）。

t4. setup 成功后 → call_command("check")（boot 里程碑，review-1 终极目标）→ pytest --collect-only → tox baseline（Gap C）。

t5. **prod-gate 并行**（不阻塞 boot，但 runtime 必须解）:
   - SAML: 查 prod 是否真配 SAML IdP provider（不只 ENABLE_THIRD_PARTY_AUTH）。不用 → t2 stub 留；用 → 装 python3-saml + 解 dm.xmlsec（1-2d）。
   - coursegraph: 查 prod 是否用 coursegraph/Neo4j。不用 → py2neo=None stub 留；用 → 真 fix（1-2d）。

t6. **开 py36-boot-fixes 分支提交真 fix**（master 工作树 uncommitted，按规矩开分支）:
   - 真修（ur/except/raise/cStringIO/long/import/exec/codejail）→ commit
   - 打桩（coursegraph/saml onelogin stub）→ 单独标 deferred commit，别混进 fix

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: t1-t4 用 lms.envs.test（SQLite），无需 MySQL/Mongo。真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. **code fixes 开分支提交，打桩单独标 deferred，migrations 不内联 removal 分支**。
4. **boot/fix 验证真跑 django.setup()+sed 验行+pip show 验 pin，不只信 fix 表** —— pymongo silent downgrade 只读 fix 表看不出（本轮活测抓到）。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+真输出（贴 traceback/pip show，非"OK"）/ 判定 / 下一步」。先做 t1（扩 constraint + 强制 pymongo 3.9.0 + pip show 验全 pin），再 t2（stub/装 onelogin + 重跑 setup 贴输出）。setup 真成功才报"boot 通过"，check 通过报"里程碑达成"。
```
