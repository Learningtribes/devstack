# Py3 迁移 — 执行审查第六轮 (Execution Review 6)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 Batch 1 落地（`batch1-core-result-20260723.md`）
> 验证方法: 进 `py36-batch1` 容器（agent 实际用的容器）真跑 pip show + import，非读文档
> 结论一句话: **13 核心 ✅ 真达成；但 shapely/ldap 真依赖被误跳 + mysqlclient 偏离 pin 且 DB 连接未验 + git 包未装，进 tox 过早。**

---

## 1. 验证证据（py36-batch1 实测）

13 核心包真 installed + import OK: django 1.11.29 / celery 3.1.25 / kombu 3.0.37 / pymongo 3.9.0 / mongoengine 0.10.0 / mysqlclient 2.1.1 / python-memcached / elasticsearch 1.9.0 / redis 2.10.6 / lxml 5.4.0 / Pillow / PyYAML / six 1.17.0。agent 的核心 claim **属实**。

未装（实测 ModuleNotFoundError）: **shapely / ldap** + 全部 git 包（django_celery / rest_framework / oauth_provider / ora2 / lbmdone_xblock 等）。

## 2. 重点 1 — mysqlclient 2.1.1 vs 1.4.6

装了 + MySQLdb import OK，但两问题:
- **(a) 偏离文档 pin**: `dependency-bridge-analysis` 定 1.4.6（dual Py2/3 真桥），agent 装了 2.1.1（Py3-only，2022 版）。对 Py3-only env 功能 OK（`import MySQLdb` 两版都提供），但丢 dual-compat 桥属性。建议 pin 回 1.4.6，或留 2.1.1 但作为 conscious decision 记录。
- **(b) import ≠ DB 连接**: 2.1.1 远新于 Django 1.11（EOL 2020，只测过 mysqlclient 1.3.x/1.4.x）。运行时连接（charset/SSL/参数）**未验**。
- **必须**: 跑真 DB-connect smoke —— `django.setup()` + `DJANGO_SETTINGS_MODULE` + 真连 devstack MySQL (`edx.devstack.mysql:3306`) + 跑一条 `SELECT 1`。import OK 不等于 DB 层 OK。

## 3. 重点 2 — 全量未完成理由

分类大体合理（test 包/已知阻塞/egg mismatch），但 **shapely + ldap 被误当良性"C 扩展 build dep"跳过**:

| 包 | platform 消费者（非测试）| 裁决 |
|---|---|---|
| **shapely** | `common/lib/capa/capa/responsetypes.py:36 from shapely.geometry import MultiPoint, Point`（CAPA 几何题型）| 🔴 真运行时依赖，需装 `libgeos-dev` |
| **ldap** | `lms/envs/aws.py:25 import ldap` + `common/djangoapps/third_party_auth/ldap_auth.py:8`（LDAP 认证）| 🔴 真运行时依赖，需装 `libldap2-dev libsasl2-dev` |
| pygraphviz | 0 platform 引用 | ✅ 可跳（transitive/unused）|
| gevent | 0 platform 引用 | ✅ 可跳 |

"与 Python 版本无关"技术上对，但 shapely+ldap 是**未完成的真实运行时依赖** —— env 在 CAPA + LDAP auth 上不完整。

## 4. 重点 3 — 下一步优先级

agent 提"lbmdone + tox baseline"**过早**。进 tox 前还差:
1. **git 包安装**（21 个，runbook §1 从 Py2 devstack 容器提取）—— tox 需全装好的 env
2. **shapely + ldap**（apt build deps + 装）—— CAPA + LDAP 运行时
3. **mysqlclient DB-connect smoke**（重点 1b）
4. **lbmdone backport patch**（运行时 XBlock，CMS GRADABLE_BLOCKS）

然后才 tox py3 allow-fail baseline（Gap C）。agent 跳过了 1/2/3。

## 5. 裁决

- 13 核心 ✅ 真达成（实测，agent claim 属实）
- mysqlclient ⚠️ 偏离 pin 1.4.6→2.1.1 + DB 连接未验
- shapely/ldap ❌ 真依赖被误跳，需补（CAPA + LDAP auth）
- git 包 ❌ 未装，待 runbook §1 提取
- 优先级 ⚠️ lbmdone+tox 过早，前面还差 git/shapely/ldap/DB-smoke

---

## 6. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第六轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-6-20260723.md
—— 先读 §1 验证证据 + §2-§4 三重点。

裁决速览（实测 py36-batch1，非读你的文档）:
- 13 核心 ✅ 真达成（agent claim 属实）。
- 但 mysqlclient 偏离 pin（1.4.6→2.1.1）+ DB 连接未验；shapely/ldap 真依赖被误跳；git 包未装。
- 进 tox baseline 过早 —— 前面还差 4 件。

你这轮补做（按序，全部在 py36-batch1 容器）:

o1. git 包安装（21 个）: 用 runbook §1 从 Py2 devstack 容器（edx.devstack.lms venv）提取已装实物，或修 egg metadata 后 pip install from git。清单见 batch1-core-result §"未完成的 git 包" + py36-git-layer-probe（8 已验过 import + 3 auth 验过 + lbmdone/ora2 待 patch）。装后逐个 `import` 真验（不只装）。

o2. shapely + ldap（真运行时依赖，非可跳）:
   - shapely: apt-get install -y libgeos-dev libgeos-c1v5 → pip install shapely。验 import + capa responsetypes 不崩。
   - ldap: apt-get install -y libldap2-dev libsasl2-dev → pip install python-ldap。验 import + third_party_auth/ldap_auth 不崩。
   消费者: capa/responsetypes.py:36（CAPA 几何题型）、lms/envs/aws.py:25 + third_party_auth/ldap_auth.py:8（LDAP 认证）。

o3. mysqlclient DB-connect smoke: django.setup() + DJANGO_SETTINGS_MODULE + 真连 devstack MySQL（edx.devstack.mysql:3306，DB 名用独立 py3 schema，见约束1 共享 DB 安全）+ 跑 SELECT 1。2.1.1 远新于 Django 1.11，import OK 不等于连接 OK。若连不上 → 试 pin 回 1.4.6（dual 桥，贴近 Django 1.11 时代）。

o4. lbmdone-xblock backport patch（运行时 XBlock，CMS GRADABLE_BLOCKS）: 装 importlib_resources backport + patch fork 的 `import importlib.resources` 为 try/except，或升 XBlock 版本。0.5d。

做完 o1-o4 → 才进 tox py3 allow-fail baseline（Gap C，OEP-7 rung 2）。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: Py3 env 首次 migrate 前独立 DB 名/schema 或 lock，否则毁 Py2 devstack 数据。o3 的 DB-connect smoke 用独立 py3 schema，别碰 Py2 数据。
2. Py3 env 独立不动 Py2 devstack。
3. 迁移修专用分支，migrations 不内联 removal 分支。
4. Py3 兼容验证真跑 import，不只 grep（grep 漏 import 重组；django-cas urllib reorg 教训）。
5. diff/版本自跑 git/pip 验证，别照搬文档（本会话多次纠正过 agent 报告）。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+输出 / 判定 / 下一步」。先做 o1（git 包）—— 它是 env 完整的最大缺口。o1-o4 全绿、env 真功能完整后再报回，那才到 tox 的起点。
```
