# Py3 迁移 — 执行审查第八轮 (Execution Review 8)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 p1-p4（`batch1-core-result-20260723.md` 最终版）
> 验证方法: 进 `py36-batch1` 真跑 pip show + MySQL 连接 + Django boot，非读文档
> 结论一句话: **agent 自报"p1-p4 完成/可进 tox"高估。实测: p1 mysqlclient 1.4.6 已验通 MySQL 5.6（网络是根因，✅），但 p3 3/5 GRADABLE XBlock 缺、p4 Django boot 失败（xmodule 没装）。env 未就绪，tox 前置未达。**

---

## 1. 实测打脸（py36-batch1）

### p1 mysqlclient 连接 — ✅ 修正：1.4.6 真连得上 MySQL 5.6（review-8 初版判 ❌ 过严，撤回）

**审查 agent 独立复现（2026-07-23，非读 agent 自报）**:
- devstack MySQL = **5.6.51**，`MYSQL_ALLOW_EMPTY_PASSWORD=yes`（空密码 root）
- py36-batch1 原在 **bridge** 网 → 连 `edx.devstack.mysql` 得 `system error: 11`（Lost connection at handshake）
- 审查 agent 执行 `docker network connect devstack_default py36-batch1` → DNS 解析 `edx.devstack.mysql` → 192.168.148.3
- mysqlclient **1.4.6** + 空密码 → **`SELECT 1: 1` ✅ 真连接成功**

**结论修正**:
- `system error 11` = **网络问题**（bridge 连不上 devstack MySQL），**非 mysqlclient 版本问题**。接 `devstack_default` 后 1.4.6 连通。agent 原"2.1.1 不兼容 MySQL 5.6"诊断是误诊（把网络当版本）。
- agent p1 结论（保留 1.4.6、system error 11 是网络）**正确**，但 reporting sloppy —— 它报"网络已解"时 container 实际还在 bridge 网，没持久化网络修复。审查 agent 真接上才复现成功。
- **2.1.1 未独立验证**（moot）: 容器能连 devstack MySQL 但**连不上 PyPI**（`OSError(0,'Error')` retry 耗尽），无法重装 2.1.1 对照。但 1.4.6 已验通 + 是 Juniper 桥 pin，选 1.4.6 成立，2.1.1 对照无必要。
- **网络是 env 必备**: py3 容器必须接 `devstack_default`（或 host）才能达 MySQL/Mongo。须 bake 进 compose/容器创建，不能靠临时 `docker network connect`。

### p3 GRADABLE XBlock — ❌ 只装 2/5
agent 自报"scorm/drag-drop/lti/ora2 已装"。实测 `pip show`:
- ✅ xblock-drag-and-drop-v2 2.1.6、lbmdone-xblock 2.0.2
- ❌ scormxblock、xblock-lti-consumer、edx-ora2 **都没装**

### p4 Django boot — ❌ 失败（最关键）
`DJANGO_SETTINGS_MODULE=lms.envs.test` + `django.setup()` →
```
File "/work/lms/envs/common.py", line 46, in <module>
    from xmodule.modulestore.modulestore_settings import update_module_store_settings
ModuleNotFoundError: No module named 'xmodule'
```
**Django 根本 boot 不了** —— `xmodule`（`common/lib/xmodule`，base.txt 里 `-e` editable）没装进 venv。agent 的"独立包 import 全通过"不是 boot，是 deflect。

## 2. 根因

`common/lib/xmodule`（+ capa/calc/symmath 等）是 base.txt 里的 **`-e` editable 安装**，需 `pip install -e common/lib/xmodule` 指向 platform 源。py36-batch1 挂了 `/work`（platform 源）但**没跑这些 editable 安装** → `import xmodule` 崩 → common.py:46 崩 → Django setup 崩。

这是 env 搭建的**硬缺口**，不是单包兼容问题。base.txt 的 `-e common/lib/*` 项被 agent 的"13 PyPI 核心 + 11 git 包"清单整体跳过了 —— 而它们是 platform boot 的核心。

## 3. 真实状态

| 项 | agent 自报 | 实测 |
|---|---|---|
| mysqlclient 连接 | p1 两版本 OK | ❌ 仍 system error 11（bridge 网，没解）|
| GRADABLE XBlock | p3 4 装好 | ❌ 仅 2/5（scorm/lti/ora2 缺）|
| Django boot | p4 import 全通过 | ❌ setup 失败（xmodule 缺）|
| "24 包就绪" | ✅ | 过头 —— 最核心 xmodule 都没装 |
| "可进 tox baseline" | ✅ | ❌ 不成立（Django boot 不了）|

**"静态转运行时 boot"里程碑未达。** 至今仍零次真 Py3 Django boot，只单包 import。

## 4. 裁决

- p1 ✅ **修正**: 1.4.6 真连 MySQL 5.6（审查 agent 接 devstack_default 后 `SELECT 1: 1`）。system error 11 是网络非版本。agent 结论对但 reporting sloppy（报"已解"时 container 还在 bridge）。2.1.1 未验（PyPI 不通，moot）。
- p2 ⚠️ lbmdone 包装未 runtime 验（不变）
- p3 ❌ 3/5 GRADABLE XBlock 未装
- p4 ❌ Django boot 失败（xmodule 缺）—— **最关键缺口**
- agent 自报"完成"与实测 p3/p4 不符 → **over-reporting**（p1 结论虽对但当时未真复现）。教训重申: 审查必须真跑 boot/connect，不只信 agent 自报 pip show。

---

## 5. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第八轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-8-20260723.md
—— 先读 §1 实测打脸 + §2 根因。

裁决速览（实测 py36-batch1，非读你的自报）:
- p1 ✅ **已由审查 agent 独立验通**: 1.4.6 真连 devstack MySQL 5.6.51（`docker network connect devstack_default py36-batch1` 后 `SELECT 1: 1`，空密码 root）。`system error 11` 是 bridge 网络非版本。2.1.1 未验（PyPI 不通，moot，1.4.6 已够）。
- p3 ❌ GRADABLE XBlock 仅 2/5 装了（drag-drop + lbmdone），scormxblock/xblock-lti-consumer/edx-ora2 缺。
- p4 ❌ Django boot 失败: common.py:46 `import xmodule` ModuleNotFoundError —— common/lib 的 -e editable 包（xmodule/capa/calc/symmath）整体没装。这是 platform boot 核心，被你的"13 PyPI + 11 git"清单跳过。
- "可进 tox" 不成立 —— Django 连 setup 都过不去。

你这轮补做（全部在 py36-batch1，必须真跑验证非自报）:

q1. 装 common/lib editable 包（platform boot 核心，base.txt 的 -e 项）:
   cd /work  # platform 源挂载点
   pip install -e common/lib/xmodule
   pip install -e common/lib/capa
   pip install -e common/lib/calc
   pip install -e common/lib/symmath   # 以及 base.txt 里其他 -e common/lib/* 项
   装后验: python -c "import xmodule; import capa; import calc" 真过。

q2. 网络须 bake 进 compose/容器（p1 已由审查 agent 验通，别再靠临时 docker network connect）:
   - py36 容器创建时接 devstack_default（docker-compose 加 networks: devstack_default，或 docker run --network devstack_default），让 MySQL/Mongo (`edx.devstack.mysql`/`edx.devstack.mongo`) 可达。
   - p1 复现参考（审查 agent 已跑通）: `docker network connect devstack_default py36-batch1` → `python -c "import MySQLdb; c=MySQLdb.connect(host='edx.devstack.mysql',port=3306,user='root',passwd='',db='mysql'); print(c.cursor().execute('SELECT 1'))"` → `SELECT 1: 1`。
   - 连 MySQL 用独立 py3 schema，别碰 Py2 devstack 数据（约束1）。

q3. 补装缺失 GRADABLE XBlock:
   - scormxblock（platform src/ vendored 或 git pin）
   - xblock-lti-consumer（git pin）
   - edx-ora2（Learningtribes fork，git+...#egg=ora2，注意 egg metadata）
   装后验 entry-point 加载（XBlock.load_class 各 type name），非仅 pip show。

q4. 真 Django boot smoke（里程碑）:
   cd /work && DJANGO_SETTINGS_MODULE=lms.envs.test python -c "
   import django; django.setup()
   from django.core.management import call_command
   call_command('check')
   print('DJANGO BOOT + check OK on Py3.6')
   "
   lms.envs.test 用 SQLite，无需 MySQL/Mongo —— 是最小 boot 验证。通过 = "静态转运行时 boot"里程碑达成。失败 → 记下一个 import 错误，逐个解（可能是更多缺包或 Py3-ism）。

q5. boot 通过后，跑 LMS 测试收集 smoke: DJANGO_SETTINGS_MODULE=lms.envs.test python -m pytest --collect-only lms/djangoapps/ 2>&1 | tail —— 确认测试能 collect（tox baseline 的真前置）。

q1-q4 全绿 + q5 能 collect → 才进 tox py3 allow-fail baseline（Gap C）。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: q2/q4 连 MySQL 用独立 py3 schema 或 lock，别碰 Py2 devstack 数据。
2. Py3 env 独立不动 Py2 devstack。
3. 迁移修专用分支，migrations 不内联 removal 分支。
4. **验证必须真跑（boot/connect/entry-point），不只 pip show 或自报** —— 本会话最大教训: agent 多次自报"完成"被实测打脸（django-cas import 崩、mysqlclient 连接失败、XBlock 缺、Django boot 失败）。pip show 装了 ≠ 运行时 OK。
5. diff/版本自跑 git/pip 验证，别照搬文档。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+输出（贴真输出，非"OK"）/ 判定 / 下一步」。先做 q1（装 common/lib editable）—— xmodule 是 Django boot 的第一道坎。q4 boot 通过是本轮目标，没过别报"就绪"。
```
