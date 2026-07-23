# Py3 迁移 — 执行审查 (Execution Review)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 任务 A（3.6 探针）+ scoped Batch 1 + DCC PRs 状态，由执行 agent 完成后交接
> 输入: `py36-probe-result-20260723.md` + `review-verdict-20260723.md` + `gh pr view` 实测 + 代码级 grep
> 结论一句话: **3.6 判定对；scoped Batch 1 基本对但补 mongoengine 5-file smoke；DCC 三个 ready / #2348 仍需 review / M4.4-B 仍未切。**

---

## 1. 3.6 探针证据 — 充分支撑方向判定，缺最后一发

### 成立的核心
`import kombu.async` 在 3.6 PASS / 3.8 SyntaxError —— load-bearing 证据，正确（async 关键字边界 3.7）。8 个核心包（Django 1.11.29 / celery 3.1.25 / kombu 3.0.37 / pymongo 3.9 / python-memcached 1.59 / elasticsearch 1.9 / redis 2.10.6 / PyYAML 5.3.1）在 3.6 单独安装全过。

### 4 个 base.txt 阻塞项的"非 3.6 特有"判定 — 核验正确
| 包 | 问题 | 核验 |
|---|---|---|
| edx-ora2 | `#egg=edx-ora2` 与 metadata `ora2` 不匹配 | ✅ base.txt line 28+41 确认（且重复出现两次，另一打包问题）|
| xblock-done | `#egg=xblock-done` 与 metadata `lbmdone-xblock` 不匹配 | ✅ base.txt line 44 确认 |
| edx-sga | `#egg=edx-sga` 同型 | ✅ base.txt line 24 确认 |
| beautifulsoup==3.2.1 | 2010 老包，"3.6 无 wheel" | ✅ platform 代码 **0 文件直接 import 老 bs3**（bs4 已被 4 文件使用）；bs3 仅是 pynliner 的 transitive dep，**非 platform 代码改动**。纯 Python sdist 不需 wheel，"无 wheel"措辞略误导 |

**→ 共享成本对 3.6 vs 3.8 中性，不削弱 3.6 判定。** 决策逻辑（3.6 省 celery+Django、shared costs cancel）成立。

### 缺的一发
探针测了"核心包单独装" + "全量 base.txt 跑出 4 个阻塞"，但**未明确记录"4 个修复后全量 install 跑到干净 resolve"**。残留风险：4 个的 transitive 闭包里可能藏 3.6 专有 wheel 缺口（某包有 3.8 wheel 但只 3.6 sdist 不可建）。

**建议**: 应用 4 修复后跑一次完整 `pip install -r base.txt` 到无错，坐实 transitive 闭包在 3.6 干净。Batch 1 的 `pip install` 步骤自然就验，但要在判定记录里写明"已确认全量 resolve"。

---

## 2. Scoped Batch 1（~2d）— 漏 mongoengine smoke；bs 升级是伪成本

### 正确跳过的（与 dependency-bridge-analysis §5 3.6 路线一致）
- ~~celery 4.4.7 + kombu 4.6.11~~ —— celery 3.1 留
- ~~edx-celeryutils fork~~ —— celery 留则无需 fork
- ~~61 `@task`→`@shared_task` 迁移~~
- ~~Django 1.11+Py3.8 灰桥 smoke~~ —— 1.11 官方支持 3.6，灰桥转白

### 留下的（对，但有漏）
pymongo 3.9.0 / mysqlclient 1.4.6 / python-memcached 1.59 / 3-4 个 egg 修复 / beautifulsoup —— 全对。

**漏 1（应补）: mongoengine 0.10.0 的 5 文件定点 smoke。** `dependency-bridge-analysis.md` §5（3.6 路线）明确写了"直换 + 5 文件 smoke（0.10.0 在 Py3.x 待验）"。Juniper 在 Py3.5 验过 0.10.0+3.9，3.6 更近，但 0.10.0 早于官方 Py3 支持，仍需对这 5 文件跑 import+CRUD smoke:
- `lms/djangoapps/dashboard/{models,git_import,sysadmin}.py`
- `lms/djangoapps/dashboard/tests/test_sysadmin.py`
- `common/lib/xmodule/xmodule/modulestore/mongoengine_fields.py`

~0.5d，补进 Batch 1。

**漏 2（轻）: Django 1.11 在 3.6 的 boot verify。** 灰桥转白后不再是风险门，但一次 `django.setup() + call_command('check')` 是 0.5d 廉价保险，确认 Hawthorn 实际 settings 能 boot。保留为 verify 非 gate。

### ~2d 估时裁决
bs 升级是伪成本（0 代码改动），pymongo/mysqlclient/memcached 是 pin swap（~0.5d），egg 修复（~0.5d），加 mongoengine smoke（0.5d）→ ~1.5-2d **成立**，bs 项不会撑破估时。

---

## 3. DCC PRs 状态 + M4.4-B — #2348 被高估

实测 `gh -R Learningtribes/platform pr view`（2026-07-23）:

| PR | 状态 | mergeable | reviewDecision | 裁决 |
|---|---|---|---|---|
| #2322 embargo | OPEN | MERGEABLE | **APPROVED** | ✅ 可 merge |
| #2323 badges | OPEN | MERGEABLE | **APPROVED** | ✅ 可 merge |
| #2324 support+zendesk | OPEN | MERGEABLE | **APPROVED** | ✅ 可 merge（T2 解冲突确认）|
| #2348 external_auth+entitlements | OPEN | MERGEABLE | **REVIEW_REQUIRED** | ⚠️ **仍需 review，未批准** |

### 关键纠正
handoff/brief 把 #2348 列为 "MERGEABLE / M4.4-A" —— **MERGEABLE 只表示无合并冲突，不等于可 merge**。它的 `reviewDecision=REVIEW_REQUIRED`，还没拿到 review approval。DCC 四个里 #2348 是落后者：**三个（2322/2323/2324）ready，#2348 还差 review**。

影响 rebase 顺序：#2348 落地前，M4.4-A 的 external_auth/entitlements 删除未上 master，依赖它的 Phase 4/5 分支不能干净 rebase。

### M4.4-B（teams SPLIT + program_enrollments）
open PR 列表里**无对应 PR** —— 与 brief "未切" 一致，确认仍未启动。阻塞 teams / program_enrollments / verify_student 的 Phase 4/5 现代化。真实未解阻塞，状态分析正确。

### Phase 4/5 PRs
#2357-2361（Phase 4）、#2362-2365（Phase 5）全 OPEN + MERGEABLE 但 `reviewDecision` 为空（标题带 `[DRAFT!!!]`）—— 草稿态，未进 review。rebase 依赖 DCC 先落 master。

**链路**: DCC 3 个 ready merge → #2348 补 review + merge → Phase 4/5 rebase 上干净 master → M4.4-B 单独切（无 PR，待启动）。

---

## 4. 文档卫生 gap

handoff 说"执行文档已更新顶部注明 target 3.6"，但读 `review-verdict-20260723.md` 顶部（§1 line 40、§2 任务 A line 46-91）—— **仍是"任务 A 最先做、决定 target"的待办态**，没标 DONE。会让接手 agent 误以为还要跑探针。

**建议**: 在 verdict §1 顶部 + §2 任务 A 加一行:
```
✅ DONE 2026-07-23: 3.6 探针通过，target=3.6，证据见 py36-probe-result-20260723.md
```
避免重复劳动。（若更新已在别的 doc 如 py3-environment-strategy.md，则在 verdict 顶部加交叉引用。）

---

## 5. 建议补的确认动作（给执行 agent）

| 序 | 动作 | 理由 |
|---|---|---|
| a | 4 修复后跑一次干净全量 `pip install -r base.txt` 到无错 | 坐实 transitive 闭包在 3.6 干净（探针缺的最后一发）|
| b | Batch 1 加 mongoengine 0.10.0 的 5 文件 import+CRUD smoke | dependency-bridge §5 明确要求，0.10.0 早于官方 Py3 支持 |
| c | verdict §1 顶部 + §2 任务 A 标 DONE + target=3.6 | 防 agent 重跑探针 |
| d | #2348 推进 review approval | 它是 DCC 四个里唯一未批准，阻塞 M4.4-A 落 master |
| e | （可选）Django 1.11 在 3.6 的 `django.setup()+check` boot verify | 0.5d 廉价保险 |

---

## 6. 裁决汇总

- **3.6 判定**: ✅ 成立。证据充分支撑方向，补动作 a 坐实最后一发。
- **scoped Batch 1 ~2d**: ✅ 基本成立。补 mongoengine smoke（b），bs 升级是伪成本不撑破估时。
- **DCC**: 三个 ready / #2348 仍需 review / M4.4-B 仍未切。brief 对 #2348 的"MERGEABLE=可 merge"是高估，已纠正。
- **下一步优先级**: a（全量 resolve 确认）→ b（mongoengine smoke）→ Batch 1 落地 → 任务 D（tox py3 allow-fail baseline，攻 Gap C）。#2348 推 review 与 Batch 1 可并行。
