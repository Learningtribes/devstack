# 交接给执行 agent — drive run failures (Gap C step 4)

> **SUPERSEDED 2026-07-27.** Do not execute the R20 `637/827/626` baseline or the “push 6 commits” step in this file. Use `docs/handoff-prompt-20260723.md` plus `docs/progress-plan-20260724.md`, which contain the current HEAD `3159585` and verified `722/1445/84/586` baseline.

> 作用：复制下方 `---` 后全文粘给执行 agent。R20 恢复 + 4 clean commit 完成，重心转 drive 637 run failures → 0。
> 配套：`progress-plan-20260724.md`（状态）、`execution-review-19-20260724.md`（modernize 失误 + 教训）、`execution-review-18-20260724.md`（tox baseline 里程碑）。

---

你是 Hawthorn Py3 迁移的执行 agent。前序（审查 agent R1-R20）已完成: boot 里程碑 + tox baseline + 从 modernize-source 失误恢复 + 4 clean commit。重心现转 **drive run failures → 0（OEP-7 step 4）**。

## 入口文档（先读）
- `devstack/docs/progress-plan-20260724.md` — 最新状态 + 演化表 + next steps
- `devstack/docs/execution-review-19-20260724.md` — **modernize-source 失误教训（必读，避免重犯）**
- `devstack/docs/execution-review-18-20260724.md` — tox baseline 里程碑

## 当前状态（R20，boot-verified）

- ✅ **boot + check 0 issues**
- ✅ 工作树干净，**6 commit 在 py36-boot-fixes（未 push）**:
  - `967954f` + `cb1ef5b`（你的 boot fix）
  - `95edf103c0e`（15 systematic Py2→3 fix + setup.cfg vendored skip）
  - `925087d87d6`（stdlib reorg: urlparse/cPickle/HTMLParser/urlencode）
  - `0f6853935ae`（contextlib.nested polyfill —— 64 error 真源是 contextlib.nested 非 drf-nested-routers）
  - `e9263a41cf9`（**test-only** modernize 666 test 文件）
- collect **1480 / 626 errors**
- run **637 failed / 827 passed / 626 errors**（test 面 1464 runnable）
- **827 真 Py3 测试通过**（地基）

## ⚠️ 必读教训（R19，避免重犯）
1. **容器 `/edx/app/edxapp/edx-platform` 是 host `platform/` 的 bind-mount** —— docker exec 写操作直改 host，docker cp 冗余。改前 `docker inspect py36-build --format '{{range .Mounts}}{{.Source}}{{end}}'` 查。
2. **`python-modernize -wn` 绝不可跑 source**（absolute→relative import 转换冲突 manual boot fix，崩 boot）。**test-only 安全**（已做）。剩余 source 修必须手工 Edit。
3. **每改必验 boot**（`django.setup() + call_command("check")` → "0 issues"），不只信 fix 表。

## 你这轮推进（按序）

**p1. push py36-boot-fixes**（6 commit）到 origin —— 保住成果:
```bash
cd /Users/noahwang/workspace/hawthorn/platform
git push origin py36-boot-fixes
git log --oneline origin/py36-boot-fixes..HEAD  # 验空 = 真 push
```

**p2. drive 637 run failures（核心，OEP-7 step 4）**:
```bash
# --tb=line 聚类根因
docker exec py36-build bash -c 'cd /edx/app/edxapp/edx-platform && \
  DJANGO_SETTINGS_MODULE=lms.envs.test python3 -m pytest \
  --continue-on-collection-errors --tb=line -q 2>&1' > /tmp/tbline.txt
# 按错误消息聚类
grep -oE "[A-Z][a-zA-Z]*(Error|Exception): .*" /tmp/tbline.txt | \
  sed -E "s/^[A-Za-z]+(Error|Exception): //; s/[0-9].*//g; s/'[^']*'/X/g" | \
  sort | uniq -c | sort -rn | head -20
# 按源文件聚类
grep -oE "/edx/app/edxapp/edx-platform/[^:]+\.py:" /tmp/tbline.txt | \
  sort | uniq -c | sort -rn | head -15
```
找系统性根因（单文件/单行打中多测试）→ **手工 Edit 修（source）**，每修 docker exec 验 boot + 重跑 baseline。预期 top: attr-error / name-error（unicode/reduce 残留）/ not-callable / does-not-support-indexing。

**p3. collect 626 → 低**（剩余长尾）:
- cStringIO/StringIO → io（BytesIO/StringIO 区分，手工）
- tests.integration/unit 相对 import 结构
- provider 第三方 hashlib 12（patch provider 包 或 pin）
- 其他长尾 broken test 文件 skip

**p4. ORA2/6F 真解（尾部风险，~70K SLOC）**:
- openassessment 从 settings 移除是 deferred stub，ORA2 是 GRADABLE_BLOCKS 运行时 XBlock
- 6F ora2+proctoring 无上游 Py3 fork —— patch LT fork / wait / replace 决策
- 唯一仍可能显著推后时间线的尾部风险

**p5. prod-gate 4 stub**（需 prod 配置，agent 无法独决）:
- SAML（onelogin/dm.xmlsec）/ coursegraph（py2neo/Neo4j）/ enterprise / jwt —— 查 PROD 是否启用，不用→stub 留，用→真解

## 硬约束（review-verdict §5 + R19 教训）
1. 共享 DB 安全: 测试用 lms.envs.test（SQLite），真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支，commit+push。
4. **boot 验证每改必做**（django.setup + check → "0 issues"），不只信 fix 表。审查 agent 多轮活测抓 over-reporting。
5. **`python-modernize` 只 test 文件，绝不 source**（R19 教训）。source 修手工 Edit。
6. **容器 = host bind-mount**，docker exec 直改 host，改前查 mount。
7. diff/版本自跑 git/pip 验证。
8. platform 其他分支不动。

## 回报格式
每步「做了什么 / 命令+真输出（贴 tbline 聚类 + baseline 数字 + boot 确认）/ 判定 / 下一步」。先 p1（push）+ p2（--tb=line 聚类 637 failures，贴 top 根因），聚类定 p2 修法。
```
