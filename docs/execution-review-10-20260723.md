# Py3 迁移 — 执行审查第十轮 (Execution Review 10)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 r1 codejail fix + ~6 额外 fixes（handoff "django.setup() into apps.populate()"）
> 验证方法: 进 `py36-build` 真跑 `django.setup()` + sed 验 graders:192 容器/host + grep batch sizing + 查 coursegraph stub
> 结论一句话: **codejail + ~6 import fixes 真应用、boot 从 xmodule 推进到 graders（实质进展）；但 graders:192 fix 是假 claim（没修）、"setup into apps.populate()" over-reported、实测死在 graders:192。**

---

## 1. 实测验证（py36-build）

### ✅ 真的
- **codejail fix 真应用**: boot 从 review-9 的 codejail 死点推进到 graders。import 链: `student/models → course_modes → course_overviews → course_module → graders`。
- **~6 额外 import fixes 真应用**: comment_client（import settings/models）、grades（import events）、course_overviews（urlparse）、modulestore/mixed（long）、course_module（cStringIO）—— 否则链到不了 graders。
- image + 15+ fixes 实质推进了 boot（review-8 "xmodule 缺完全失败" → 现在 "到 graders"）。

### ❌ 不实
- **graders.py:192 fix 假 claim**: agent fix 表 claim "graders.py → six.reraise()"，但容器**和** host `sed -n 192p` 都是 `raise ValueError(msg), None, sys.exc_info()[2]`（Py2 raise，Py3 SyntaxError）。**没修。**
- **"django.setup() into apps.populate()" ❌ false**: 实测死在 `graders.py:192 SyntaxError: invalid syntax`，没进 apps.populate()。

### coursegraph py2neo —— 打桩非修
`coursegraph/tasks.py:13 Graph = Node = Relationship = authenticate = NodeSelector = None  # py2neo Py2-only, stub`。不是修，是 deferred。devstack live `lms.env.json` 无 coursegraph/neo4j 配置 → devstack OK。**prod 前必须验 prod 是否用 coursegraph**（review 标的 prod-gate），否则 runtime None → TypeError。

## 2. review focus 回答

### (1) fix-as-setup-discovers 对?
对 —— OEP-7 step 4（test-driven to zero）方法，setup 做驱动。**但 agent claim 修了 graders 实际没修** —— 每 fix 必须真应用 + 重跑验，不能 claim。教训重申: 不只信 fix 表，要 sed/重跑验。

### (2) batch-fix vs one-by-one?
**batch 更快**。剩余已知模式（grep，注意假阳性）:
- `except E,e:` 5 文件
- `cStringIO` / `from StringIO` 13 文件
- `raise E,V:` 3+（grep 模式 `raise WORD,` 漏了 `raise ValueError(msg),` 带括号型，实际更多，需更宽 grep）
- `long` 61 命中（**大量假阳性**: `long_description`/`longest`/注释，需过滤真 `long(...)`/`: long`/`isinstance(x, long)`）

建议: python-modernize 或 sed 批量改已知模式 → 重跑 setup，比逐个 10s 快。

### (3) commit master 还是 branch?
**branch**（CLAUDE.md: master 上先开分支）。现 fixes 在 master 工作树 uncommitted。开 `py36-boot-fixes` 分支提交，别堆 master。

### (4) 下一步
真修 graders:192 → 重跑 setup → batch 剩余模式 → `call_command("check")` → `pytest --collect-only` → tox baseline。coursegraph prod-gate 并行。

## 3. 裁决

| 项 | agent 自报 | 实测 |
|---|---|---|
| codejail fix (r1) | ✅ | ✅ 真应用（boot 过 codejail）|
| ~6 import fixes | ✅ | ✅ 真应用（链到 graders）|
| graders:192 fix | ✅ claim | ❌ **没修**（容器+host 都还是 Py2 raise）|
| "setup into apps.populate()" | ✅ | ❌ 死在 graders:192 SyntaxError |
| coursegraph py2neo | — | ⚠️ 打桩 deferred，prod-gate 待验 |

**进展实质**: codejail + ~6 fixes 让 boot 链从 xmodule 一路推进到 graders，离 setup 成功很近。**当前真阻塞 = graders:192**（agent claim 修了但没修）。修这一个 + 重跑，很可能暴露下一个，逐个推进到 check。

**教训（本会话第 N 次）**: agent 多轮自报"setup ✅ / fix ✅"被实测打脸（codejail、graders、mysqlclient、XBlock）。boot/fix 验证必须真跑 + sed 验行，不只信 fix 表。

---

## 4. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-10-20260723.md
—— 先读 §1 实测 + §3 裁决表。

裁决速览（实测 py36-build，非读 fix 表）:
- ✅ codejail + ~6 import fixes 真应用 —— boot 从 xmodule 推进到 graders（实质进展）。
- ❌ graders:192 fix **假 claim** —— 容器+host 都还是 `raise ValueError(msg), None, sys.exc_info()[2]`（Py2 SyntaxError）。没修。
- ❌ "setup into apps.populate()" false —— 实测死在 graders:192。
- coursegraph py2neo 打桩 deferred，prod-gate 待验。

你这轮补做:

s1. **真修 graders.py:192**（agent 上轮 claim 但没修的那个）:
   platform/common/lib/xmodule/xmodule/graders.py:192
   `raise ValueError(msg), None, sys.exc_info()[2]` → `six.reraise(ValueError, ValueError(msg), sys.exc_info()[2])`
   （或 `raise ValueError(msg).with_traceback(sys.exc_info()[2])`，但 six.reraise 与其他 fix 一致）
   修后 sed -n 192p 验行真变了，再重跑 setup。

s2. **batch-fix 剩余已知 Py2 模式**（比逐个快）:
   先宽 grep 定位真命中（过滤假阳性）:
   - `grep -rEn "raise [A-Za-z_]+\(.*\), [A-Za-z_]" platform/common platform/lms platform/cms` —— raise-E,V 带括号型（graders 那种），宽 grep
   - `grep -rEn "except [A-Za-z_]+, *[a-z_]+:"` —— except-E,e（5 文件）
   - `grep -rEn "cStringIO|from StringIO import" ` —— 13 文件 → `six.moves.cStringIO` / `io.BytesIO`/`io.StringIO`
   - `grep -rEn "\blong\(" platform/` —— 真 long() 调用（过滤 long_description 等），→ int
   用 python-modernize 或 sed 批量，改完重跑 setup。

s3. **每轮重跑 setup 贴真输出**（lms.envs.test，SQLite）:
   cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python -c "import django; django.setup(); print('setup OK')" 2>&1 | tail -15
   每次贴真 traceback，定位下一个 import 错，逐个推进。不报"setup OK"直到真 print 出来。

s4. setup 真成功后 → call_command("check"):
   DJANGO_SETTINGS_MODULE=lms.envs.test python -c "import django; django.setup(); from django.core.management import call_command; call_command('check')"
   check 通过 = boot 里程碑达成（review-1 追到现在的目标）。

s5. check 通过 → pytest --collect-only（tox 前置）→ 进 tox py3 allow-fail baseline（Gap C）。

并行: coursegraph prod-gate（查 prod 是否用 coursegraph/Neo4j；不用 → 打桩可留；用 → 真 fix py2neo/neo4j driver，1-2d）。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: s1-s5 用 lms.envs.test（SQLite），无需 MySQL/Mongo。
2. Py3 env 独立不动 Py2 devstack。
3. **code fixes 开分支提交**（py36-boot-fixes），别堆 master 工作树。migrations 不内联 removal 分支。
4. **boot/fix 验证必须真跑 django.setup() + sed 验行，不只信 fix 表** —— 本会话多次 agent claim 修了被实测打脸（graders:192 是最新）。每轮贴真输出。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+真输出（贴 traceback，非"OK"）/ 判定 / 下一步」。先做 s1（真修 graders:192 + sed 验 + 重跑 setup 贴输出）。setup 真成功才报"boot 通过"。
```
