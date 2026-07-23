# Py3 迁移 — 执行清单（供 reasonix + deepseek-v4-pro 继续）

> Date: 2026-07-23 (updated after T1+T2+T3-partial)
> Workspace root: `/Users/noahwang/workspace/hawthorn/`
> master: `8db868ed589` | 共享 base: `embargo-removal-squashed` = `21690c0c708`

---

## 进度日志

- ✅ **T1.1** 6C `capa/xqueue_interface.py` 2 处→推，CI 绿
- ✅ **T1.2** 6A `xmodule/contentstore/content.py` 1 处→推，CI 绿
- ✅ **T1.3** 其余 6 分支全量复扫 py3 compile: 0 errors
- ✅ **T2** #2324 rebase 到 master → MERGEABLE (APPROVED)
- ✅ **任务 A** 3.6 探针通过 → **target=Python 3.6**，celery 3.1 保持不动
- ✅ **任务 B** mongoengine 0.10.0 在 3.6 CRUD 验证通过
- ✅ **review-verdict §1 标 DONE**
- ⏭️ **T3** DCC 合并 + 8 分支 rebase（#2322/#2323/#2324 APPROVED, #2348 REVIEW_REQUIRED）
- ⏭️ **Batch 1 落地** — py36-base.txt + pymongo 3.9 + mysqlclient + memcached
- ⏭️ **任务 D** — tox py3 allow-fail baseline（攻 Gap C）

---

## 0. 背景与现状

- 全部 Phase4/5 PR 的 GitHub base = `embargo-removal-squashed`（已由 master 改为 squash-base 降噪）
- Phase 5 已开 4 个 PR：#2362 6D、#2363 6B、#2364 6C、#2365 6A
- #2364/#2365 的 Python 3 Syntax Check 已修复（CI 等待中）
- #2324 已解冲突，MERGEABLE

### PR / 分支 / worktree 对照

| PR | 分支 | worktree | 批次 | GH CI | mergeable |
|:---:|------|------|------|------|------|
| #2357 | `student-py3-analysis` | `platform-student-py3` | 4-5E | ✅ | MERGEABLE |
| #2359 | `courseware-py3` | `platform-courseware-py3` | 4-5F | ✅ | MERGEABLE |
| #2360 | `instructor-py3` | `platform-instructor-py3` | 4-5D | ✅ | MERGEABLE |
| #2361 | `contentstore-py3` | `platform-contentstore-py3` | 4-5G | ✅ | MERGEABLE |
| #2362 | `phase5-6d-apis` | `platform-phase5-6d-apis` | 5-6D | ✅ | MERGEABLE |
| #2363 | `phase5-6b-core` | `platform-phase5-6b-core` | 5-6B | ✅ | MERGEABLE |
| #2364 | `phase5-6c-libs` | `platform-phase5-6c-libs` | 5-6C | ✅ | MERGEABLE |
| #2365 | `phase5-6a-xmodule` | `platform-phase5-6a-xmodule` | 5-6A | ✅ | MERGEABLE |
| #2322 | `embargo-removal` | `platform-embargo-removal` | DCC | ✅ | APPROVED |
| #2323 | `badges-removal` | `platform-badges-removal` | DCC | ✅ | APPROVED |
| #2324 | `support-zendesk-removal` | `platform-support-zendesk-removal` | DCC | ✅ | APPROVED |
| #2348 | `m4-4a-external-auth-entitlements` | `platform-m4-4a-external-auth-entitlements` | DCC M4.4-A | ✅ | REVIEW_REQUIRED |

---

## 通用约定

- Python 命令一律 `uv run`
- 提交：先 `git status` → `git add <file>`，禁止 `git add -A`
- 提交信息英文
- 每条任务：本地验证 → 推送 → 确认 CI → 更新本清单

---

## T1 🔴 P0 — 修复 6C/6A 的 Py3 语法遗漏 ✅ DONE

- [x] T1.1 — 6C `xqueue_interface.py` 2 处 `except E, e:` → `as`
- [x] T1.2 — 6A `content.py` 1 处 `except Exception, exc:` → `as`
- [x] T1.3 — 其余 6 分支 changed-files py3 compile: 0 errors
- [x] Push + CI 等待

---

## T2 🟠 P1 — #2324 解冲突 ✅ DONE

- [x] Rebase onto `origin/master`
- [x] 冲突 1: `lms/urls.py`（goodhabitz URL 介入）→ 删除 support URL block，保留 goodhabitz
- [x] 冲突 2: `courseware/views/views.py`（rest_framework import）→ 合并两方 import
- [x] Push force-with-lease → MERGEABLE
- [x] 交叉引用检查: `_record_feedback_in_zendesk` 零残留, `create_zendesk_ticket` 零残留

---

## T3 🟡 P1 — DCC 合并 + Phase4/5 rebase ⏭️ 待人工

- [ ] 合并 #2322 embargo → 8 分支 base 回切 master + rebase
- [ ] 合并 #2323 badges → 修 certificates/extended_api 引用
- [ ] 合并 #2324 support+zendesk → 修 courseware/instructor 引用
- [ ] 删除 `embargo-removal-squashed` 集成分支

---

## T4 🟡 P2 — Jenkins pr-head aborted 定性 ⏭️

- [ ] 查看 Jenkins 日志判定基础设施 vs 真失败

---

## T5 📝 P2 — 更新 inventory ✅ DONE（本次）

- [x] §2 Phase 5 已开 PR 状态补全
- [x] §3 PR 对照表更新
- [x] #2324 状态更正
- [x] 6C/6A CI 状态更新

---

## T6 ⏭️ 后续（本轮不阻塞）

- [ ] M4.4-B（teams SPLIT + program_enrollments）
- [ ] Phase4 blocked 模块（teams/PE/dcc/verify_student）
- [ ] Phase5 6E（~15K SLOC）
- [ ] Phase5 6F（vendored src/ ~70K SLOC）
- [ ] Py3.8 Django 运行时

---

## 验收标准

1. ✅ #2364/#2365 Py3 Syntax Check 已修复
2. ✅ 全 8 分支 `except ... ,` 零残留，changed-files py3 compile 通过
3. ✅ #2324 恢复 MERGEABLE
4. ✅ inventory 已更新
