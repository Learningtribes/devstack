# Py3 迁移 — 执行审查第十三轮 (Execution Review 13)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 RV1/RV2 + G1-G4 提交 + pytest collect 基线（handoff "4 commits pushed + 1181/823 baseline"）
> 验证方法: docker exec 验 DRF 版本 + git log 验 4 commit+push + pytest collect 实跑
> 结论一句话: **✅ G1-G4 commit+push + RV1 全验证；但 DRF 被静默替换 edx-fork-3.6.3→vanilla-3.11.2（丢 patch + 不在 constraint，review-11 风险再现）；823 collect 基线 error 真实但数字未独立复现（需 --continue）。**

---

## 1. 验证证据

### ✅ commits + push 全验证
| repo | branch | commit | push | 裁决 |
|---|---|---|:---:|---|
| devstack | noah-py2-m-chip-master | `7a02619` | ✅ | ✅ |
| platform | py36-boot-fixes | `967954f` + `cb1ef5b`（2 commit, 110 files）| ✅（`origin/py36-boot-fixes..` 空）| ✅ |
| migration_discussion | migration_discussion | `d097f59c15c` | ✅ | ✅ |
| browser-acceptance-harness | browser-acceptance-harness | `b6cbd6660f9` | ✅ | ✅ |

platform 回 master（`d25bb55f579` embargo commit）✅。RV1 DRF `basename` accepted（3.11.2）✅。RV2 openassessment 标 deferred ✅。

### ⚠️ 新发现: DRF 静默替换（review-11 silent-upgrade 风险再现）
- **DRF = vanilla 3.11.2**（`pip show` Home-page django-rest-framework.org，PyPI wheel），**不是** git-layer probe 报的 "edx fork 3.6.3"
- base.txt 原 pin `git+...edx/django-rest-framework.git@1ceda7c#egg=djangorestframework==3.6.3`（edx fork，有 edx 专属 patch）
- agent `pip install` 从 Tsinghua mirror 拉了 vanilla 3.11.2，**丢了 edx fork patch**
- **DRF 不在 constraint**（只锁 Django/celery/kombu/pymongo/mysqlclient/mongoengine）→ 正是 review-11 标的 silent-upgrade 风险，DRF 这次中招（上次 pymongo 降回 2.9.1）
- 需办: (a) constraint 加 DRF pin；(b) 验 edx fork patch 是否还需（vanilla 3.11.2 是否覆盖 edx 定制）；(c) DRF 3.11.2 + Django 1.11 runtime 验（3.11 最低支持 1.11，但可能移除 edx 代码用的 API）

### ⚠️ pytest collect 1181/823 基线
- collection error 实测确认: `ImportError: No module named 'urlparse'`（Py2-ism 在某 test import）
- 但**未独立复现 "1181 collected / 823 errors" 确切数字** —— 实跑遇第一个 collection error（urlparse）就停，没出 summary。要 `--continue-on-collection-errors` 才能跑全基线
- 823 errors 是 Gap C（OEP-7 step 4）工作队列 —— drive 823→0

## 2. 裁决

| 项 | agent 自报 | 实测 |
|---|---|---|
| G1-G4 commit+push | 4 repos pushed | ✅ 全验证（含 py36-boot-fixes 2 commit）|
| RV1 DRF basename | accepted | ✅（DRF 3.11.2）|
| RV2 openassessment deferred | 标注 | ✅ |
| platform 回 master | d25bb55 | ✅ |
| DRF 版本 | 3.11.2 | ✅ 但**静默替换** edx fork 3.6.3，丢 patch，不在 constraint |
| collect 1181/823 | baseline | ⚠️ error 真实，数字未独立复现（需 --continue）|

**agent 这轮诚实**（commit/push/RV1/RV2 全对），但 DRF 静默替换是 agent 自己也可能没意识到的（pip 没 pin 拉了 vanilla）—— 再次证明 constraint 不全的代价。

---

## 3. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十三轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-13-20260723.md
—— 先读 §1（DRF 静默替换 + collect 基线）。

裁决速览（实测）:
- ✅ G1-G4 commit+push + RV1/RV2 + 回 master 全验证 —— 这轮诚实。
- ⚠️ DRF 被静默替换: edx-fork-3.6.3 → vanilla-3.11.2（PyPI wheel，丢 edx patch，不在 constraint）。review-11 silent-upgrade 风险再现。
- ⚠️ collect 823 errors 真实（urlparse 确认），但 1181/823 数字未独立复现，需 --continue 跑全。

下一阶段（重心: 测试环 Gap C + DRF 收口）:

v1. **补 constraint 锁 DRF + 其他 git fork dep**（防再漂移）:
   /root/.pip/constraints.txt 加 djangorestframework（及其他怕漂移的 git fork dep）。
   决策: DRF 用 vanilla 3.11.2 还是回 edx fork 3.6.3? —— 见 v2。

v2. **DRF 3.11.2 vs edx fork 3.6.3 决策**:
   (a) 查 edx DRF fork @1ceda7c 比 vanilla 3.6.3 多哪些 patch（git log diff）
   (b) 验这些 patch 在 vanilla 3.11.2 是否仍需（DRF 3.11 可能已含或 edx 代码已不依赖）
   (c) 验 DRF 3.11.2 + Django 1.11 runtime: 跑 LMS DRF 视图 smoke（不只 check）—— DRF 3.11 移除了部分旧 API（如 Serializer old field 声明），可能崩
   决策: 留 3.11.2（若 patch 不需 + runtime OK）→ constraint pin 3.11.2；或回 edx fork 3.6.3（`-e git+...@1ceda7c`，需验 Py3.6 兼容 + base_name 而非 basename）。

v3. **pytest --collect-only --continue-on-collection-errors 跑全基线**:
   cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python -m pytest --collect-only --continue-on-collection-errors -q 2>&1 | tail
   确认 1181/823 数字 + 分类 collection error（urlparse/iteritems/except-E,e/import-absolute 等 Py2-ism 模式）。823 是工作队列。

v4. **tox py3 allow-fail baseline（Gap C / OEP-7 rung 2）**:
   建 tox.ini py36 env（allow fail）+ 跑全量，记失败基线。这是暴露 csv/base64/hashlib 21 文件 + 其余运行时 Py3-ism 的机制（py_compile 盲区，review-1 就标）。

v5. **ORA2/6F stub 真解（prod-gate，尾部风险）**: openassessment 从 settings 移除 + 空 stub 是 deferred。ORA2 是 GRADABLE_BLOCKS 运行时 XBlock。6F ora2+proctoring ~70K SLOC 无上游 Py3 fork —— patch/wait/replace 决策。这是唯一仍可能显著推后时间线的尾部风险。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支（已 push），新 fix 继续 commit 到该分支。
4. **验证真跑（pytest --continue 全基线 + DRF runtime smoke），不只信数字/自报** —— 本会话多次活测抓 over-reporting + silent 漂移（pymongo、DRF）。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动（现 master，别动）。

回报格式: 每步「做了什么 / 命令+真输出 / 判定 / 下一步」。先做 v1+v2（DRF constraint + 决策 + runtime smoke），再 v3（--continue 全基线），数字确认后 v4 tox。
```
