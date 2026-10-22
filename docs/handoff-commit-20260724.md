# 交接给执行 agent — 提交 + 提交前验证

> 作用: 复制下方 `---` 之后全文粘给执行 agent。任务: 完成本会话累积的提交 + 提交前验 2 个 review 点。
> 背景: Py3 迁移 boot 里程碑已达成（`call_command("check")` 0 issues，review-12 VERIFIED）。现需把累积工作提交并 push。

---

你是 Hawthorn Py3 迁移的执行 agent。本会话（审查 R1→R12）累积了大量未提交工作 + 2 个提交前必须验的 review 点。先做验证，再提交。

## 0. 入口文档（先读）
- `devstack/docs/execution-review-12-20260723.md` — boot 里程碑审查（VERIFIED）+ 5 stub deferred 风险登记
- `devstack/docs/django-boot-fixes-20260723.md` — 30+→60+ fix catalog
- `devstack/docs/handoff-prompt-20260723.md` — 最新交接（check 通过）
- `devstack/docker/py36/BUILD.md` — py36 镜像构建脚本

## 1. 未提交清单（全 worktree 扫描结果）

### platform `py36-boot-fixes` 分支（主战场）
- **已 commit**: `967954f68de fix(py3): django boot compatibility fixes (41 files)` —— 本地有，**push 状态存疑**（`origin/master..HEAD` 有此 commit → 可能未 push，handoff 称"pushed"待验）。
- **68 项 modified（未提交，commit 后又改的）**: 21 lms/djangoapps + 17 common/djangoapps + 14 openedx/core + 8 openedx/features + 4 common/lib + 3 cms/djangoapps + 1 lms/envs。多数是 Py2→3 fix（ur/except/raise/cStringIO/urlparse/import/builtins/codejail/third-party patches）。**本次工作，应提交。**
- **32 项 untracked**: 多数 pre-existing junk（`ws3.json`/`ws.json`/`uv.lock`/`pyproject.toml`/`node-v16.tar.gz`/`platform.code-workspace`/`platform-student-py3/`/`scripts/*.csv`/`scripts/*.sql`）—— **非本次工作，别提交**。部分 docs（docs/specs, docs/reviews, docs/migration, docs/discussions, docs/claude-skills-*）也 pre-existing。`requirements/edx/py36-base.txt` untracked（platform 副本，canonical 在 devstack，可不提交）。

### devstack `noah-py2-m-chip-master`
- **2 modified**: `docs/handoff-prompt-20260723.md` + `requirements/py36-base.txt`
- **14 untracked**（全本次工作）: `docker/py36/`（Dockerfile+BUILD.md+README.md+py36-base.txt）+ `docs/execution-review-6..12`（7 份）+ `docs/batch1-core-result` + `django-boot-fixes` + `py36-image` + `py36-base-gap-analysis` + `docs/pr-2347-{verification,review-comment}`

### platform-migration_discussion（1 untracked）
- `docs/migration_discussion/12-oep7-conformance-assessment-20260723.md`

### platform-browser-acceptance-harness（9 untracked）
- `.claude/skills/browser-acceptance/checklists/pr-{2322,2324,2334,2335,2347,2357,2359,2360,2361}.yml`

### 其余 17 worktree —— 全 clean（0/0）
py3-integration / py3-m5-grades / triboo-analytics / preflight-ur-regex / hawthorn-codebase-wiki / student/courseware/instructor/contentstore-py3 / phase5-6{a,b,c,d} / embargo/badges/support-zendesk-removal / m4-4a / m4-module-removal。

## 2. ⚠️ 提交前必验的 2 个 review 点（硬阻塞）

### RV1. 验 DRF 3.6.3 是否认 `basename`（在 py36-build 容器）
platform py36-boot-fixes 改了 3 个 urls.py 的 `base_name='x'` → `basename='x'`（DRF `register()` API）。但 DRF 锁在 edx fork **3.6.3**，`base_name` 是 3.6.3 的参数，`basename` 是 DRF 3.9+ 才有。**若 DRF 3.6.3 不认 `basename`，runtime `router.register(...)` 会 TypeError**（`call_command("check")` 过是因为这些 urls 可能在 lms.envs.test 不被 import —— check 过 ≠ runtime 安全）。

验证（在 py36-build 容器）:
```bash
docker exec py36-build bash -lc '
python -c "
import rest_framework
print(\"DRF\", rest_framework.VERSION)
from rest_framework.routers import DefaultRouter
r = DefaultRouter()
try:
    r.register(r\"test\", object, basename=\"x\")
    print(\"basename: ACCEPTED\")
except TypeError as e:
    print(\"basename: REJECTED →\", e)
    r.register(r\"test\", object, base_name=\"x\")
    print(\"base_name: ACCEPTED (DRF 3.6.3 用 base_name)\")
"'
```
- 若 `basename` REJECTED → `base_name→basename` 改动是错的，**revert 3 个 urls.py**（DRF 3.6.3 用 `base_name`）。
- 若 ACCEPTED（edx fork backport 了）→ 改动对，保留。

### RV2. openassessment 从 settings 移除 是 conscious 还是临时
`lms/envs/common.py` 删了 OPTIONAL_APPS 里 5 行 openassessment 注册（`openassessment`/`.assessment`/`.fileupload`/`.workflow`/`.xblock`）。**不只是 stub，是从 settings 移除 ORA2**。
- 这与 deferred stub 清单（review-12 §2）的 `openassessment 空 stub` 一致 —— boot 靠移除+stub 过。
- ORA2 是 GRADABLE_BLOCKS 运行时 XBlock（open-response 题型，课程广泛用）—— runtime 含 ORA2 的课程会崩。连 6F ora2+proctoring ~70K SLOC（无上游 Py3 fork）。
- **记录**: 这个改动是 deferred（boot 通过用），不是永久移除。在 commit message / deferred 清单里写明 "openassessment removed from OPTIONAL_APPS as deferred stub (ORA2 runtime pending 6F resolution)"。prod 前必须真解。

## 3. 提交分组（验完 RV1/RV2 后执行）

**G1. devstack（2 M + 14 ??）一个 commit**:
```bash
cd /Users/noahwang/workspace/hawthorn/devstack
git add docs/handoff-prompt-20260723.md requirements/py36-base.txt docker/ \
  docs/execution-review-6..12-20260723.md docs/batch1-core-result-20260723.md \
  docs/django-boot-fixes-20260723.md docs/py36-image.md docs/py36-base-gap-analysis.md \
  docs/pr-2347-verification.md docs/pr-2347-review-comment.md
git commit -m "Py3 migration: boot milestone docs + py36 image build artifacts"
```

**G2. platform py36-boot-fixes（68 M）第二个 commit**（验完 RV1 决定是否含 3 urls.py）:
```bash
cd /Users/noahwang/workspace/hawthorn/platform
# selective add —— 只加本次 fix，别 git add -A（32 untracked junk 不提交）
git add common/ lms/djangoapps/ openedx/ cms/djangoapps/ lms/envs/common.py
# 若 RV1 判 basename 错 → 先 git checkout 那几个 urls.py revert
git commit -m "fix(py3): additional boot compat fixes (post 967954f)"
git push origin py36-boot-fixes   # 确认 push（handoff 称已 push 待验）
```
**注**: 32 untracked 里 pre-existing junk（ws*.json/uv.lock/pyproject.toml/node-v16.tar.gz/platform.code-workspace/platform-student-py3/scripts/*.csv 等）**绝不提交**。只挑本次 fix。

**G3. platform-migration_discussion（1）单独 commit**:
```bash
cd /Users/noahwang/workspace/hawthorn/platform-migration_discussion
git add docs/migration_discussion/12-oep7-conformance-assessment-20260723.md
git commit -m "docs: OEP-7 conformance assessment"
git push origin migration_discussion
```

**G4. platform-browser-acceptance-harness（9）单独 commit**:
```bash
cd /Users/noahwang/workspace/hawthorn/platform-browser-acceptance-harness
git add .claude/skills/browser-acceptance/checklists/
git commit -m "feat(acceptance): PR checklists for DCC + Phase4/5 PRs"
git push origin browser-acceptance-harness
```

## 4. 硬约束
1. **selective add，绝不 `git add -A`/`git add .`**（CLAUDE.md）—— platform 32 untracked 多数是 pre-existing junk。
2. **RV1 必须先验** —— `base_name→basename` 若错 revert，别把错改动 commit 进去。check 过 ≠ runtime 安全。
3. **openassessment 移除标 deferred**，commit message 写明，别当永久 fix。
4. **每个 worktree 自己的分支提交**，不跨 worktree。push 后 `git log origin/<branch>..HEAD` 验空（确认真 push 上去）。
5. 平台 code fix 在 `py36-boot-fixes` 分支（已建），别回 master。
6. migrations 不内联 removal 分支。

## 5. 回报格式
每步「做了什么 / 命令+真输出 / 判定 / 下一步」。
- 先 RV1（DRF basename 验）+ RV2（确认 openassessment deferred 标注）—— 贴真输出。
- 再 G1-G4 提交，每 commit 后 `git log --oneline -1` + `git status --short | wc -l` 确认残留。
- push 后 `git log origin/<branch>..HEAD` 验空（真 push）。
- 全部完成后报回每个 worktree 的 commit SHA + push 状态。
```
