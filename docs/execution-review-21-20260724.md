# Py3 迁移 — 执行审查第二十一轮 (Execution Review 21) — .claude/ 污染 + 清理

> Date: 2026-07-27 · Reviewer: Claude (审查 agent)
> 审查对象: agent 2 新 commit（`94af75d` track .decode、`5af72a4` config_models + .claude 污染）
> 结论: `94af75d` ✅ 干净；`5af72a4` ❌ 纯污染（config_models bogus + 178 `.claude/` 文件误提交）。已 forward 清理（`a829f8a6`）。

---

## 1. review 发现

### `94af75d` ✅ 干净
`track/middleware.py` + `track/views/__init__.py`: 移除 `.decode('latin1')`（Py3 str 无 .decode；Py3 Django request.META 已返 str）。正确。

### `5af72a4` ❌ 纯污染 commit
两个问题:
1. **config_models fix 是假的**: message claim `config_models/models.py unicode→str (57 failures)`，但该文件早在 `4fb3da23` 移到外部 repo（platform 无此文件）。diff 为空，claim 不实。
2. **178 `.claude/` 文件误提交**: 整个 `.claude/skills/pptx/`（Anthropic LICENSE.txt + SKILL.md + scripts + OOXML schemas）+ 其他 .claude/ 文件被 `git add` 扫进 platform repo。`.gitignore` 未排除 `.claude/`，未挡住。

5af72a4 非-.claude 改动 = 全是 .claude/skills/pptx/ 内容 → **commit 实为 100% 污染，无真 platform fix**。

## 2. 清理（forward，不改 pushed history）

commit `a829f8a6c37`:
- `git rm --cached -r .claude/`（untrack 178 文件，磁盘保留 —— Claude 继续用）
- `.gitignore` 加 `.claude/`（防再犯）
- push

验证: tracked .claude = 0，磁盘 .claude/ = yes，gitignore = 1。

5af72a4 留 history（pushed，未 force-push）。合并前若需净 history 可 rebase drop（用户节奏）。

## 3. 教训（落盘，防再犯）

1. **`git add` 必须按具体路径**（CLAUDE.md 既有规矩 "Never git add -A or git add ."）—— 这次 `git add` 扫进 .claude/ 中招。每次 `git status` 确认 + 按文件路径 add。
2. **`.gitignore` 必须排除 `.claude/`** —— Claude 工具私有（skills/settings/Anthropic license），非产品代码。已加。
3. **commit message 应反映真改动** —— 5af72a4 claim config_models fix 实为空，误导 review。commit 前看 `git diff --cached --stat` 确认 staged 内容与 message 一致。

## 4. 当前 py36-boot-fixes（8 commit，全 pushed）
`967954f` + `cb1ef5b`（agent boot fix）+ `95edf103`（15 systematic）+ `925087d8`（stdlib reorg）+ `0f68539`（nested polyfill）+ `e9263a4`（test-only modernize）+ `0ef4ffa`（hmac/bytes）+ `a829f8a6`（untrack .claude）。

boot ✅ 0 issues，工作树干净，无 .claude 污染。
