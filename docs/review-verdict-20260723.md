# Py3 Migration — 审查结论 + 执行交接 (Review Verdict & Execution Handoff)

> Date: 2026-07-23 · Reviewer: Claude (review agent)
> **本文件自包含** —— 另一个 agent 只读此文件即可继续执行，无需先读 review-brief 或 7 份核心文档。
> Input provenance: `review-brief-20260723.md` + 7 core docs + OEP-7 source + 代码级 grep 验证（3 个并行证据 agent 产出）。

---

## 0. 自导航（agent 必读）

```
工作根目录: /Users/noahwang/workspace/hawthorn/

主仓库:    platform/                   (master 分支; remotes: origin=Learningtribes/platform, upstream=openedx/edx-platform)
整合分支:  platform-py3-integration/   (分支 py3-integration, 8 分支已合并, 0 冲突; merge-base ae5411201c3)
依赖文档:  devstack/docs/               (本文件所在)
迁移文档:  platform-migration_discussion/docs/migration_discussion/
上游参考:  platform/.claude/skills/python3-migration/references/
            ├── oep-0007-bp-migrate-to-python3.rst   (OEP-7 原文, Status: Obsolete)
            └── juniper-reference.md
上游分支:  platform 内 git log upstream/open-release/juniper.master (Py3-only, target Py3.5)
           git log upstream/open-release/ironwood.master (最后 Py2-only)

Py38 容器已存在: 见 platform/CLAUDE.md "Python 3.8 Testing" —— .claude/skills/python3-migration/scripts/setup-py38-container.sh
测试命令: uv run paver test_system -s lms --fail-fast --disable-migrations
          uv run paver test_lib -C --fasttest
```

**Git 快捷**:
```bash
git -C /Users/noahwang/workspace/hawthorn/platform worktree list
git -C /Users/noahwang/workspace/hawthorn/platform-py3-integration status
gh -R Learningtribes/platform pr list --state open --json number,title,headRefName,mergeable
```

---

## 1. 执行状态一句话

计划设计稳健、OEP-7 主轴一致。**Python target=3.6 已定**（探针 a→n 5 轮走完，依赖可建性端到端闭合：PyPI 197 包 + git 层核心包全验、3/4 auth 过、django-cas ❌ 真阻塞已 sizing）。**至今仍零次 Py3 运行时启动**（仅 `py_compile`，OEP-7 rung 2 之前）—— 重心现转 Batch 1 落地 + Gap C 测试环。所有时间线在"建起测试环"之前不可信。

> ✅ DONE 2026-07-23: 3.6 探针全轮闭合（a→n）。target=3.6，celery 3.1+kombu 3.0 不动，省 ~5-7d。依赖 characterization 闭合，无"未测"缺口。2 个已知运行时阻塞带 fix: lbmdone-xblock（`importlib.resources`）+ django-cas（`iteritems()`）。详见 `py36-probe-result` / `py36-git-layer-probe` / `py3-dep-residual-workstream` / `execution-review-5`。
>
> **下一阶段（重心转移）**: ① Batch 1 落地（~2d）+ ② lbmdone/django-cas 运行时 fix + ③ coursegraph/SAML prod-gate 调查 + ④ 任务 D（tox py3 allow-fail baseline，攻 Gap C）。探针阶段结束，不再需要探针轮次。

---

## 2. 立即执行计划（P0，按序）

### 任务 A：Python 3.6 依赖可建性探针【最先做，决定 target】

**为什么先做这个**：target 3.8 同时制造了两大风险（Q1 celery 4.4 迁移 5-7d + 61 `@task` + edx-celeryutils fork；Q3 Django 1.11+Py3.8 灰桥官方从未测）。`async` 关键字边界在 **3.7**（非 3.8），Django 1.11 官方止于 **3.7** —— 故 **3.6 是唯一同时让 celery 不动 + Django 1.11 官方支持**的版本。3.8 也 EOL（2024-10），EOL 不构成选 3.8 的理由。唯一未知：2026 年依赖树在 3.6 上能否 resolve。

**探针命令**:
```bash
# 起 py36 容器
docker run -it --network host --name py36-probe \
  -v "/Users/noahwang/workspace/hawthorn/platform:/work" -w /work \
  python:3.6-bullseye /bin/bash

# 容器内
python -m pip install "pip<21.0" "setuptools<45"
pip install -r requirements/edx/base.txt 2>&1 | tee /tmp/py36-install.log
# 关键：记录哪些包无 3.6 wheel / 哪些版本被强制升降
```

**判定树**:
- **大体 resolve**（仅少数包降版本即可）→ target 改为 **3.6**。**省掉 Q1 celery 全部工作 + Q3 灰桥 smoke**。跳到任务 C（直接建测试环）。把 pin 变更记录到 `devstack/docs/py36-probe-result-<date>.md`。
- **大面积不可 resolve** → 确认 3.8 是被迫的；在 `py3-environment-strategy.md` 写明"target 3.8 因 3.6 dep 树不可建"（目前文档无此论据）。继续任务 B。

### 任务 B：Django 1.11.29 + Py3.8 smoke spike【仅当任务 A 判 3.6 不可建】

```bash
# py38 容器（CLAUDE.md 已有 setup）
docker run -it --network host --name py38-tool-container \
  -v "/Users/noahwang/workspace/hawthorn/platform:/work" -w /work \
  python:3.8-bullseye /bin/bash
./.claude/skills/python3-migration/scripts/setup-py38-container.sh
source /work/.venv/bin/activate

# smoke: 能否 boot Django
DJANGO_SETTINGS_MODULE=lms.envs.devstack python -c "
import django; django.setup()
from django.core.management import call_command
call_command('check')
" 2>&1 | tee /tmp/django-py38-smoke.log
```

**关注**: `time.clock()` 移除警告、第三方 middleware（django-celery-beat/social-auth）错误、`collections.abc` 问题。
- 通过 → 灰桥转白，bridge 成立。
- 失败 → 重估是否被迫跳 Django 2.2.28（连锁切断 Py2，必须 cutover 同时升 Django）。

### 任务 C：启动 Batch 1 依赖升级【任务 A/B 出结果后】

**若 target 3.6**: 跳过 celery/kombu/edx-celeryutils 三项（不动）。Batch 1 缩为 pymongo 3.9.0 + mysqlclient 1.4.6 + （Django 1.11.29 已在）+ py36 pin 调整。估时 ~2d。

**若 target 3.8**: Batch 1 全量（见下）。估时 **5-7d**（文档原估 3-5d 偏轻）:
- celery 4.4.7 + kombu 4.6.11（**hard block**：kombu.async SyntaxError 不解决则任何 `import celery` 崩）
- edx-celeryutils fork：0.2.7 pin `celery>=3.1.25,<4.0` → fork 改 `<5.0` + 适配 3 wrapper 类（`LoggedPersistOnFailureTask`/`LoggedTask`/`chord`）的 Task 签名
- **61 处 `@task` → `@shared_task` 机械迁移**（instructor_task 单包 14 个）+ 回归
- pymongo 3.9.0（**注意文档矛盾**：juniper-dependency-comparison 说 3.9；dependency-bridge-analysis §5 说 3.13；oep-0007 说 3.12。**以 3.9 为准**，与 Juniper 一致）
- mysqlclient 1.4.6（替换 MySQL-python 1.2.5）

### 任务 D：建立 tox py3 allow-fail baseline【OEP-7 rung 2，Gap C 的核心】

Batch 1 落地、Py3 runtime 可 boot 后立即做。这是审查认定的**唯一真实方法缺口**（其余都被"answer 已知上游"放松，唯此不能）。
- 在 tox/py3 配置里开 py3，allow fail
- 跑一次全量，记录失败基线
- OEP-7 明说"将失败测试降到零"阶段"几乎必然涉及文本处理归一化" —— 即测试环是**暴露任务 E 待办的唯一机制**（`py_compile` 是盲区）

---

## 3. 跟进队列（P1–P3）

| 优先级 | 动作 | 详情 |
|---|---|---|
| **P1** | 修复 21 个 csv/base64/hashlib 文件 | 见 §4 文件清单；~1d。另 triage 未计入项：boto/S3 bytes、`__cmp__`/`cmp()`/`sort(cmp=)`（xmodule sorting）、Django TextField→CharField（上游 `897bd25b013`）|
| **P1** | 共享 DB 安全决策 | Py3 env 对共享 MySQL/Mongo 跑 migration 可能毁 Py2 devstack 数据。决策：Py3 用独立 DB 名/schema，或 migration lock。文档完全未讨论 |
| **P1** | paver + webpack + no_webpack_loader 在 Py3 验证 | 环境策略漏项；paver 是 Py2 时代工具，所有测试命令假设它工作 |
| **P2** | reconcile integration branch 计数 | 声称 770 文件/−848 删除；实测 829 文件/−4575 删除（删除偏少 5.7x，口径不一致）。修 `integration-branch-analysis.md` |
| **P2** | Gap A severity 🟢→🟡 | OEP-7 line 143-145 把 deps-first 表述为 runtime 前置（"Before converting... we need to make sure"），非 ordering。团队自己"runtime can't boot"打脸 🟢。ora2/proctoring residual 从 Gap B 移到 Gap A（它是依赖阻塞非 sequencing）|
| **P3** | 6F vendored src/ 决策 | ~70K SLOC，ora2+proctoring，无上游 Py3 fork。patch/wait/replace 三选一。尾部风险，可能推后时间线 |

---

## 4. 待修复文件清单（21 个 csv/base64/hashlib，已 grep 确认未在 integration branch 修复）

**hashlib 喂 str（15 文件）—— 应 `.encode()` 后再喂**:
- `lms/djangoapps/instructor_task/models.py:332` — `hashlib.sha1(text_type(course_id))`
- `lms/djangoapps/badges/backends/badgr.py:69` — `hashlib.sha256(slug + six.text_type(course_id))`
- `common/djangoapps/track/middleware.py:185` — `hashlib.md5(key_salt + settings.SECRET_KEY)`
- `common/djangoapps/edxmako/paths.py:58` — `hashlib.md5(":".join(str(d) for d in ...))`
- `common/lib/xmodule/xmodule/static_content.py:95,143` — `hashlib.md5(fragment)`
- （其余 10 个见 grep 证据，模式相同）

**base64 str/bytes 混用（5 文件）**:
- `cms/djangoapps/contentstore/tasks.py:739` — `base64.urlsafe_b64encode(repr(courselike_key))`（repr 返 str → TypeError；下游 `path / subdir` 因 subdir 是 bytes 再崩）
- `cms/djangoapps/contentstore/api/views/course_import.py:134` — 同 repr 模式
- `common/djangoapps/third_party_auth/pipeline.py:514` — `base64.b64encode(data_str)`
- `openedx/core/lib/api/test_utils.py:24,87` — `'Basic ' + base64.b64encode('%s:%s' % ...)`（双重 bug：str 入参 + bytes 结果拼到 str）
- `lms/djangoapps/verify_student/tests/test_ssencrypt.py`

**csv binary mode（1 文件）**:
- `lms/djangoapps/triboo_analytics/management/commands/export_problem_answers.py:202` — `open(file_path,'wb')` + `csv.writer(...)`（Py3 需 text mode）

**修复模板**（hashlib 为例）:
```python
# 前: hashlib.sha1(text_type(course_id)).hexdigest()
# 后: hashlib.sha1(text_type(course_id).encode('utf-8')).hexdigest()
```

---

## 5. 关键约束（agent 执行时遵守）

1. **不要把 3.8 当既定事实** —— 任务 A 探针结果决定 target。3.6 若可建，省掉 Q1+Q3 两大块。
2. **mongoengine 实际只用 5 文件**（573 `DoesNotExist` 命中是 DRF 噪声，不是 mongoengine）: `lms/djangoapps/dashboard/{models,git_import,sysadmin,tests/test_sysadmin}.py` + `common/lib/xmodule/xmodule/modulestore/mongoengine_fields.py`。保持 0.10.0（Juniper 验证），但在 py 容器对这 5 文件定点 smoke。文档矛盾（0.10/0.18/0.19.1）以 `juniper-dependency-comparison.md` 0.10.0 为准。
3. **pymongo target 以 3.9.0 为准**（与 Juniper 一致），非 3.12/3.13。
4. **共享 DB 风险** —— Py3 env 首次 `migrate` 前必须有独立 DB 名或 lock，否则毁 Py2 devstack。
5. **DCC PRs 阻塞 rebases**: #2322 embargo / #2323 badges / #2324 support+zendesk / #2348 external_auth+entitlements 均 APPROVED+MERGEABLE，等人 merge；merge 后 8 个 Phase 4/5 分支才能 rebase 上 master。M4.4-B（teams SPLIT + program_enrollments）未切，阻塞 teams/PE/verify_student。
6. **3.5 月基准的口径**（2026-07-23 修正：原 verdict 曾称 brief 把 3.5 月"误归于 OEP-7"——经核验 brief 并无此归因，line 208 正确标为"上游过渡期（供参考）"，该"misattribution"finding 是误报，已撤回）。真实需注意的点：brief 待审要点 #7 与 `juniper-dependency-comparison.md` 的"3.5 months / 1436 commits"是上游 **dual-stack 测试修零阶段**的实测，**预设已有可工作的 Py3 运行时**；用它作我们时间线基准为时过早（我们 Batch 1 未启动、runtime 不能 boot）。全量迁移约 ~15 个月（`oep-0007-comparison.md` §1），3.5 月只是其中一段。
7. **"已过 dual-stack 窗口故跳 tox"辩护不成立** —— 团队仍在 Py2 prod，正处 dual-stack 窗口内。跳 tox = Gap C 本身。
8. **迁移分支纪律**: 迁移修在专用分支，migrations 不内联到 removal 分支（见 feedback_migrations_dedicated_branch）。

---

## 6. OEP-7 符合度裁决（5 维 + 3 Gap，执行时参考）

5 维自评: 代码改写 six+`__future__` ✅fair ｜ 依赖 bridge 设计fair执行过乐观（Batch 1 未启动 runtime 不能 boot，Gap A 脚注自纠）｜ 测试 tox 🔴fair略understated（未到 rung 2）｜ 文本 unicode sandwich ⚠️fair略宽（机械替换做了，边界纪律未做，未作独立矩阵行）｜ caniusepython3 ❌fair（`py_compile` 与 caniusepython3 捕获不相交集，是 substitute 非 proxy）。

3 Gap 重定级: Gap A 🔴→🟢 **过激进应 🟡**（OEP-7 line 143 是 runtime 前置非 ordering）｜ Gap B 🟡→🟢 大体fair但 residual 错置（ora2/proctoring 是 Gap-A 依赖阻塞非 Gap-B sequencing）｜ Gap C 🔴→🔴 正确保留。

---

## 7. 状态快照（供 agent 判断起点）

- Phase 0-3: 完成（77 modules）
- Phase 4: 4 PRs open（#2357 student / #2359 courseware / #2360 instructor / #2361 contentstore）
- Phase 5: 4 branches pushed（phase5-6a-xmodule / 6b-core / 6c-libs / 6d-apis）
- 整合分支 `py3-integration`: 实测 829 文件 +1912/−4575（声称 770/+1886/−848，计数偏误见 §3 P2）
- `__future__` 覆盖: master ~29% → integration ~52%（仍 ~48% 文件无 `__future__`）
- compileall: ✅ Py2+Py3 全过
- paver test_system (Py2): ✅ 每模块单独过
- Py3 测试运行: **0 次**（仅 py_compile）← 这是要攻的 Gap C
