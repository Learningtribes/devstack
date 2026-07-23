# Py3 Migration — 审查总览

> Date: 2026-07-23 · 供审查 agent 快速掌握全局
> 目标: 审核当前计划的完整性、正确性、与上游 OEP-7/Juniper 的一致性

## 自导航（审查 agent 必读）

本文件是唯一入口。所有文档、worktree、仓库位置如下，可自行 `read_file` / `bash` 探索：

```
工作根目录: /Users/noahwang/workspace/hawthorn/

├── platform/                              ← 主仓库（git worktree parent, master 分支）
│   │                                        git remotes: origin=Learningtribes/platform,
│   │                                        upstream=openedx/edx-platform
│   │
│   ├── .claude/skills/python3-migration/references/
│   │   ├── oep-0007-bp-migrate-to-python3.rst    OEP-7 原文
│   │   └── juniper-reference.md                   Juniper commit/pattern 目录
│   │
│   └── (git worktree 列表见下方)
│
├── platform-py3-integration/              ← 🔑 整合分支 worktree
│   │                                        分支: py3-integration (8 branches merged, 0 conflicts)
│   │                                        基: 21690c0c708 (embargo-removal-squashed)
│   │
├── platform-student-py3/                  ← Phase 4 #2357 (student-py3-analysis)
├── platform-courseware-py3/               ← Phase 4 #2359 (courseware-py3)
├── platform-instructor-py3/               ← Phase 4 #2360 (instructor-py3)
├── platform-contentstore-py3/             ← Phase 4 #2361 (contentstore-py3)
├── platform-phase5-6d-apis/               ← Phase 5 (phase5-6d-apis)
├── platform-phase5-6b-core/               ← Phase 5 (phase5-6b-core)
├── platform-phase5-6c-libs/               ← Phase 5 (phase5-6c-libs)
├── platform-phase5-6a-xmodule/            ← Phase 5 (phase5-6a-xmodule)
├── platform-embargo-removal/              ← DCC #2322
├── platform-badges-removal/               ← DCC #2323
├── platform-support-zendesk-removal/       ← DCC #2324
├── platform-m4-4a-external-auth-entitlements/ ← DCC #2348
├── platform-m4-module-removal/            ← DCC combined M4 branch
├── platform-migration_discussion/         ← 迁移规划文档 (branch: migration_discussion)
│   │   关键文档: docs/migration_discussion/
│   │     01-status-dashboard.md             PR 状态 + DCC merge 顺序
│   │     03-runtime-environment.md          运行时版本矩阵
│   │     04-infrastructure-dependencies.md  依赖分析（因果链）
│   │     05-independent-audit.md            独立审计（celery/ES/MongoDB 修正）
│   │     08-execution-playbook.md           执行任务卡片
│   │     10-estimation-methodology.md       估时方法论
│   │     11-phase5-module-inventory-20260715.md  Phase 5 模块全量扫描
│   │     12-oep7-conformance-assessment-20260723.md OEP-7 符合性评估
│   │   关键文档: docs/specs/migration/
│   │     py3-roadmap.md                     总路线图
│   │     py3-feasibility-report.md           可行性报告
│   │
├── platform-browser-acceptance-harness/   ← Playwright 浏览器测试
│   │   checklists: .claude/skills/browser-acceptance/checklists/pr-*.yml
│   │
├── devstack/                              ← 独立仓库！Docker Compose 本地环境
│   │   关键文档: docs/
│   │     review-brief-20260723.md          ← 本文件
│   │     integration-branch-analysis.md    整合分支 + Juniper 差距
│   │     py3-environment-strategy.md       Py3/Py2 双环境方案
│   │     gap-closure-plan.md               5 个补全机制
│   │     juniper-dependency-comparison.md  Ironwood→Juniper 逐包对照
│   │     dependency-bridge-analysis.md     pip 包升级计划
│   │     upstream-juniper-patterns.md      上游代码模式对照
│   │     oep-0007-comparison.md            OEP-7 逐条对照
│   │     execution-checklist-20260723.md   执行清单
│   │     migration-inventory.md            分支/PR/worktree 全景
│   │     phase4-progress.md               Phase 4 详细
│   │     phase5-coverage-gap.md           Phase 5 覆盖度
│   │     future-import-pitfalls.md         __future__ 风险（可复用）
│   │     pyc-stale-cache-removal.md        .pyc 清理（可复用）
│   │     pr-2357-verification.md ~ pr-2361-verification.md  各模块验证报告
│   │
│   └── docker-compose.yml                  ← devstack 容器定义
│
├── platform-python3-migration/            ← (如果存在) Py3 迁移辅助
│
└── src/                                   ← pip 安装的 XBlocks + vendored 包
    ├── edx-ora2/
    ├── edx-proctoring/
    └── ...
```

**Git 快捷访问**：

```bash
# 所有 worktree
git -C platform worktree list

# 上游 Juniper/Ironwood（platform 任意 worktree 已 fetch）
git -C platform log upstream/open-release/juniper.master --oneline -3
git -C platform log upstream/open-release/ironwood.master --oneline -3

# PR 状态
gh -R Learningtribes/platform pr list --state open --json number,title,headRefName,mergeable
```

**文档读取路径格式**：所有分析文档在 `devstack/docs/` 目录下，使用绝对路径读取：

```bash
# 示例
read_file /Users/noahwang/workspace/hawthorn/devstack/docs/integration-branch-analysis.md
read_file /Users/noahwang/workspace/hawthorn/platform-migration_discussion/docs/migration_discussion/12-oep7-conformance-assessment-20260723.md
```

---

## 快速状态（30 秒版）

- **仓库**: Open edX Hawthorn (Python 2.7, Django 1.11), LearningTribes fork
- **目标**: Python 3.8
- **团队**: 1 engineer + AI
- **进度**: Phase 0-3 完成(77 modules) → Phase 4 完成 4 PRs open + Phase 5 完成 4 branches pushed
- **整合分支**: `py3-integration` (8 branches merged, 770 files, +1886/-848, zero conflicts)
- **阻塞**: DCC PRs 在 review, celery 4.4 bridge 未启动, 无 Py3 Django 运行时
- **预估**: stretch Feb 2027 (13 months), realistic Q1-Q2 2027

---

## 文档索引

### 审查核心（必读 — 今天的产出，最新状态）

| 文档 | 内容 | 字节 |
|------|------|-----|
| **`integration-branch-analysis.md`** | 8 分支合并 + 对照 Juniper 差距分析（csv/base64/hashlib 缺口） | 7.5K |
| **`py3-environment-strategy.md`** | Py3 环境与 Py2 devstack 完全隔离方案 | 7.7K |
| **`gap-closure-plan.md`** | 对照上游过渡期的 5 个补全机制 | 5.5K |
| **`juniper-dependency-comparison.md`** | Ironwood→Juniper 逐包对照 + upstream 过渡时间线 | 8.2K |
| **`dependency-bridge-analysis.md`** | pip 包 + 数据库驱动升级计划（~7天）| 6.7K |
| **`upstream-juniper-patterns.md`** | 上游 iteritems/reraise/csv 等模式逐项对照 | 8.0K |
| **`oep-0007-comparison.md`** | 与官方 Py3 迁移规范逐条对照 + 3 Gap 重定级 | 8.5K |

### 执行追踪（今天更新）

| 文档 | 内容 |
|------|------|
| **`execution-checklist-20260723.md`** | T1+T2 done ✅, T3-T6 pending, PR 状态表 |
| **`migration-inventory.md`** | 17 worktrees + 所有分支 + 依赖图 + 测试结果 |

### 历史产出（仍有效但非审查重点）

| 文档 | 内容 |
|------|------|
| `phase4-progress.md` | Phase 4 完成的 4 个模块详细 |
| `phase5-coverage-gap.md` | Phase 5 覆盖度分析（6A–6F）|
| `pr-2357-verification.md` ~ `pr-2361-verification.md` | 各模块测试验证报告 |
| `future-import-pitfalls.md` | `__future__` 四大导入风险分级（可复用） |
| `pyc-stale-cache-removal.md` | `.pyc` 残留 → RuntimeError（可复用） |

### 上游对照参考

| 路径 | 内容 |
|------|------|
| `platform/.claude/skills/python3-migration/references/oep-0007-bp-migrate-to-python3.rst` | OEP-7 原文 |
| `platform/.claude/skills/python3-migration/references/juniper-reference.md` | Juniper 参考（commit/pattern 目录）|
| `upstream/open-release/ironwood.master` | 最后一个 Py2-only release（已 fetch）|
| `upstream/open-release/juniper.master` | 第一个 Py3-only release（已 fetch）|
| `platform-migration_discussion/docs/migration_discussion/12-oep7-conformance-assessment-20260723.md` | OEP-7 符合性独立评估 |

---

## 关键事实（供审查验证）

### 代码改动

| 类别 | 数据 |
|------|------|
| Phase 4 PRs (open) | 4 (#2357 student, #2359 courseware, #2360 instructor, #2361 contentstore) |
| Phase 5 branches (pushed) | 4 (`phase5-6d-apis`, `phase5-6b-core`, `phase5-6c-libs`, `phase5-6a-xmodule`) |
| 整合分支 | `py3-integration` (770 files, +1886/-848) |
| 改动类型 | `__future__` + `six.text_type` + `six.iteritems` + `six.string_types` + `six.moves.range` + `except as` + `print()` + `reraise` |
| compileall | ✅ Py2 + Py3 全部通过 |
| paver test_system (Py2) | ✅ 每个模块单独验证通过 |

### DCC 依赖

| PR | 状态 | 阻塞什么 |
|:---:|:---:|------|
| #2322 embargo | APPROVED, MERGEABLE | 8 branches rebase onto master |
| #2323 badges | APPROVED, MERGEABLE | certificates/extended_api references |
| #2324 support+zendesk | APPROVED, MERGEABLE (rebase done) | courseware/instructor references |
| #2348 external_auth+entitlements | MERGEABLE | M4.4-A |
| M4.4-B (teams SPLIT) | 未切 | teams/PE/dcc Phase 4 modules |

### 依赖升级

| 包 | Hawthorn | Bridge target | Juniper | 差异 |
|------|------|------|------|------|
| celery | 3.1.25 | 4.4.7 | 3.1.26 | Juniper 停在 3.1（target Py3.5） |
| kombu | 3.0.37 | 4.6.11 | 3.0.37 | Juniper 没动 |
| pymongo | 2.9.1 | 3.9.0 | 3.9.0 | 一致 |
| mongoengine | 0.10.0 | 不动 | 0.10.0 | 一致 |
| MySQL 驱动 | MySQL-python 1.2.5 | mysqlclient 1.4.6 | mysqlclient 1.4.6 | 一致 |
| Django | 1.11.15 | 1.11.29 | 2.2.16 | Juniper 跳了 2.2 |
| redis | 2.10.6 | 不动 | 2.10.6 | 一致 |
| elasticsearch | 1.9.0 | 不动 | 1.9.0 | 一致 |

### 上游过渡期（供参考）

| 事件 | 日期 | Commit |
|------|------|------|
| `__future__` + `six` 最初添加 | 2018 | `4f12be08940` |
| Dual-stack tox (py27+py35) 首次启用 | 2019-09-12 | `d1728b3d6a9` |
| Py2 从 tox 移除 | 2019-12-26 | `b2046f6674e` |
| `2to3` 清理 `__future__` | 2019-12-30 | `9cf2f9f298e` |
| Dual-stack 期间: 3.5 months, 1436 commits |

### OEP-7 符合度

| 维度 | 判定 |
|------|:---:|
| 代码改写方法（six + __future__） | ✅ 一致 |
| 依赖策略（bridge version） | ✅ 比 OEP-7 更强 |
| 测试驱动（tox py2+py3） | 🔴 差距 — 未建立 |
| 文本处理（unicode sandwich） | ⚠️ 部分 — csv/base64 缺口 |
| caniusepy3k linting | ❌ 未启用（用 py_compile 替代） |

---

## 待审要点

请审查以下关键判断：

1. **celery 4.4 是否必要** — 我们 target Py3.8，Juniper target Py3.5 所以能停在 celery 3.1。如果我们可以降到 Python 3.6，celery 也可以不动？（但 3.6 已 EOL 2021-12）

2. **mongoengine 0.10.0 不升级** — Juniper 验证了 0.10.0 + pymongo 3.9 兼容。但我们用了 `mongoengine` 的哪些 API？0.10.0 是否有已知 Py3 bug？

3. **Django 1.11.29 on Py3.8** — 官方从未测试。Java 11 级别的风险。是否有更好的方案？

4. **csv/base64/hashlib 缺口** — 20 个文件是否准确？是否有遗漏的 bytes/str 边界问题？

5. **整合分支 770 files** — 我们覆盖了上游 Juniper 的 Py3 改动的多大比例？哪些关键模块被遗漏？

6. **Py3 环境策略** — 独立 venv + 独立 requirements + 共享数据库。是否有遗漏的技术障碍（如 Django 1.11 在 Py3.8 下无法连接 MySQL 5.6）？

7. **时间线** — stretch Feb 2027 vs realistic Q1-Q2 2027。上游 dual-stack 只用了 3.5 个月。我们的阻力和加速因素？
