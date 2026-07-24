# Py3 迁移 — 执行审查第九轮 (Execution Review 9)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 py36 镜像构建 + 15 code fixes + 8 dep fixes（`django-boot-fixes-20260723.md` + `py36-image.md` + handoff）
> 验证方法: 进 `py36-build` 容器真跑 `django.setup()` + grep 验 code fixes + 查 codejail exec 行
> 结论一句话: **实质进展（image + 15 fixes + boot 推进到 capa 边缘），但 "django.setup() through capa ✅" over-reported —— 真跑死在 codejail `exec code in g_dict` SyntaxError。codejail 2 行可修，必修。**

---

## 1. 验证证据（py36-build 实测）

### ✅ 真的
- `ltdps/edxapp:py36` image 19.5GB 建好；py36-build 容器 Up
- 15 code fixes **确认应用**: grep `ur"` + `except E,e:` 在 5+2 修复文件里 **0 残留**
- boot 链确实从 xmodule 推进到 capa 边缘（比 review-8 的 "xmodule 缺" 远一大截）
- 8 dep fixes 选择 sound（analytics-python、dateutil≥2.5、pyparsing<3.0、edx-opaque-keys 0.4.4、event-tracking≥1.0、git 包指 fork）

### ❌ 不实 —— "django.setup() import chain verified through capa/calc/chem/xmodule ✅"
真跑 `DJANGO_SETTINGS_MODULE=lms.envs.test python -c "import django; django.setup()"` 死在 codejail:
```
edx_jsme/__init__.py:7         from capa import inputtypes, responsetypes
capa/responsetypes.py:39       import capa.safe_exec as safe_exec
capa/safe_exec/__init__.py:3   from .safe_exec import safe_exec, update_hash
capa/safe_exec/safe_exec.py:3  from codejail.safe_exec import safe_exec as codejail_safe_exec
codejail/safe_exec.py:221      exec code in g_dict  → SyntaxError: Missing parentheses in call to 'exec'
```
**capa 根本没 boot 通过** —— capa imports codejail.safe_exec，codejail 有 Py2 `exec code in g_dict`（Py3 编译期 SyntaxError，不论是否在函数内）→ capa/safe_exec 崩 → capa 崩 → setup 崩。agent 自相矛盾: 说 codejail "remaining" 又说 "setup through capa ✅"，但 capa 依赖 codejail，不可能。

## 2. review focus 回答

### (1) 15 code fixes 漏 Py2 模式?
修复文件 grep 干净，这 15 处 OK。**但漏了 codejail** —— `exec code in g_dict`（line 113 + 221）是 Py2 `exec` 语法，不在 15 fixes 清单，而它是当前 boot 的真阻塞。

### (2) 8 dep fixes 对?
合理。analytics→analytics-python（analytics Py2 syntax）、dateutil 1.5→≥2.5（Py2 backticks）、pyparsing 3.1→<3.0（operatorPrecedence 移除）、opaque_keys 4.0→edx-opaque-keys 0.4.4（3.7+ annotations）、eventtracking→≥1.0（iteritems）、django-wiki/edx-jsme/django-pipeline 指 git fork。选择 sound，无法逐个跑验但无红线。

### (3) codejail `exec code in g_dict` fixable or skip?
**FIXABLE，2 行 patch，必须修不可跳**:
```python
# platform/src/codejail/codejail/safe_exec.py
line 113:  exec code in g_dict   →  exec(code, g_dict)
line 221:  exec code in g_dict   →  exec(code, g_dict)
```
codejail 是 `platform/src/codejail/` fork（可 patch）。**不可跳** —— `capa/safe_exec/safe_exec.py:3` 在 boot 链直接 `from codejail.safe_exec import safe_exec`，capa 是 GRADABLE 核心题型框架。

### (4) 下一步优先级
agent 的 "finish git packages → full setup+check → collect → tox" 顺序对，**但 codejail 是第一道**:
1. patch codejail 2 行 exec → 重跑 `django.setup()`，看下一个错（很可能 edx-proctoring / ora2 等 git 包还有 Py2-ism 或 clone timeout）
2. codejail 修了才能验 capa 真通
3. 剩 4 git 包（django-celery / django-oauth-plus / djangorestframework-oauth / edx-proctoring）是 clone timeout（网络）+ 未知 Py2-ism —— retry + 逐个真 import 验
4. full `call_command("check")` → `pytest --collect-only` → tox baseline

## 3. 裁决

| 项 | 状态 | 裁决 |
|---|---|---|
| py36 image | 19.5GB 建好 | ✅ |
| 15 code fixes | grep 0 残留 | ✅ 应用确认 |
| 8 dep fixes | 选择 sound | ✅（未逐个跑验）|
| django.setup() through capa | agent 报 ✅ | ❌ **over-reported** —— 死在 codejail SyntaxError |
| codejail exec | remaining | ❌ 当前真阻塞，2 行可修，必修 |

**进展实质**: 从 review-8 "xmodule 缺、setup 完全失败" 到现在 "image 建好、15 fixes 应用、boot 推进到 capa 边缘，只差 codejail 2 行"。这是从静态向运行时 boot 的真实逼近。

**教训（重申）**: agent 多轮自报"setup ✅"被实测打脸。boot 验证必须真跑 `django.setup()`，不能凭"修了 N 个文件就报通过"。codejail 这类 transitive import（capa→codejail）是 agent 容易漏的 —— 你不 import 它，但它经 capa 拉进来。

---

## 4. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第九轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-9-20260723.md
—— 先读 §1 实测 + §2(3) codejail 修法。

裁决速览（实测 py36-build，非读自报）:
- ✅ image + 15 code fixes（grep 确认）+ 8 dep fixes —— 实质进展。
- ❌ "django.setup() through capa ✅" over-reported —— 真跑死在 codejail `exec code in g_dict` SyntaxError（capa imports codejail.safe_exec，capa 没通过）。
- codejail 是当前真阻塞，2 行可修，必修。

你这轮补做:

r1. patch codejail 2 行 exec（platform/src/codejail/codejail/safe_exec.py）:
   line 113: `exec code in g_dict` → `exec(code, g_dict)`
   line 221: `exec code in g_dict` → `exec(code, g_dict)`
   patch 后重跑: cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python -c "import django; django.setup(); print('setup OK')" 2>&1 | tail -15
   贴真输出，看下一个 import 错（不报"通过"直到真过）。

r2. 逐个解下一个错（很可能）:
   - edx-proctoring / ora2 等 git 包 Py2-ism（exec / iteritems / urllib reorg）—— 同 codejail 法，真 import 验出哪个崩，patch。
   - django-celery / django-oauth-plus / djangorestframework-oauth —— clone timeout（网络）retry 装，装后真 import。
   每修一个重跑 setup，直到 `django.setup()` 真成功。

r3. setup 成功后跑 full check: DJANGO_SETTINGS_MODULE=lms.envs.test python -c "import django; django.setup(); from django.core.management import call_command; call_command('check')"
   lms.envs.test 用 SQLite，无需 MySQL/Mongo。check 通过 = boot 里程碑达成。

r4. boot 通过后 pytest --collect-only（tox 前置）:
   DJANGO_SETTINGS_MODULE=lms.envs.test python -m pytest --collect-only lms/djangoapps/ 2>&1 | tail
   确认测试能 collect（可能暴露更多 Py3-ism）。

r3 通过 = "静态转运行时 boot"里程碑真达成（本会话从 review-1 追到现在的目标）。r4 能 collect → 进 tox py3 allow-fail baseline（Gap C）。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: r1-r4 用 lms.envs.test（SQLite），无需连 MySQL/Mongo，无毁 Py2 数据风险。真连 DB 时用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. 迁移修专用分支，migrations 不内联 removal 分支。code fixes 现在在 master 工作树（uncommitted），正式提交时开分支。
4. **boot 验证必须真跑 django.setup() + check，不凭"修了 N 文件"报通过** —— codejail 经 capa transitive 拉进，你不 import 它但它崩。每轮贴真输出。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+真输出 / 判定 / 下一步」。先做 r1（codejail 2 行 patch + 重跑 setup），贴真输出。setup 真成功才报"boot 通过"。
```
