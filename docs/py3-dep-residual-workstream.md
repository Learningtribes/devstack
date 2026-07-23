# Py3 Dep 残留工作流

> Date: 2026-07-23
> 来源: base.txt 7 个阻塞 + git 层 25+ 包的 Python 3.6 探针
> 不包含在 scoped Batch 1 (~2d) 中

---

## 1. coursegraph/py2neo — 替换或移除

> ⚠️ **先查 prod 用量再 sizing**（与 §2 SAML 同纪律）

### 调查 gate
- 查 `lms/envs/aws.py` / production settings 是否启用 Coursegraph 任务
- 查 Neo4j 连接配置是否存在
- **不用 → DCC 移除评估优先。用 → 评估 py2neo 4+ / neo4j driver**

### 用量
- `openedx/core/djangoapps/coursegraph/tasks.py` + compat + test utils（3 文件）
- API: `Graph`, `Node`, `Relationship`, `authenticate`, `NodeSelector`

### 选项
- A: 升级到 py2neo 4+（API 不兼容——`NodeSelector`/`authenticate` 4.x 移除，`Graph` API 改。3 文件但 5 API 全变，**1-2d**）
- B: 换用 neo4j official driver（同需适配）
- C: DCC 移除 coursegraph（**先调查 prod 用量**；评估 2-3d）

## 2. SAML/dm.xmlsec.binding — 适配或跳过

- **入口**: `lms/envs/aws.py` → `saml2.sigver.get_xmlsec_binary`
- **路径**: `dm.xmlsec.binding` → `pysaml2` → `third_party_auth` SAML
- **问题**: `dm.xmlsec.binding==1.3.3` 的 `setup.py` 用 `print` 语句（Py3 SyntaxError）
- **步骤**:
  - 确认 prod 是否启用 SAML（`ENABLE_THIRD_PARTY_AUTH` + SAML provider config）
  - 若不用 SAML → 跳过
  - 若用 SAML → 升级 `pysaml2` + 替换 `dm.xmlsec.binding` 为 `xmlsec`
- **估时**: 0.5d（调查）+ 0.5d（若需适配）

## 3. Git 层 25+ 包 — 逐个验证（已完成）

- **真验过 8 包**: django-celery / DRF / django-pipeline / django-wiki / MongoDBProxy / pygeoip / codejail / ParsePy ✅
- **auth 3/4 过**: django-oauth-plus / django-openid-auth / djangorestframework-oauth ✅；django-cas ❌（见 §4）
- **运行时 XBlock**: lbmdone-xblock ❌（`importlib.resources` 3.6，CMS GRADABLE_BLOCKS，见汇总 #3）；acid-xblock ✅ 跳过（不在 settings）
- **未测 3（非核心）**: crowdsourcehinter（测试 XBlock）/ edx-jsme（vendored）/ recommender-xblock（废弃 0 引用）
- **egg metadata 修复**: edx-ora2 → `#egg=ora2`, xblock-done → `#egg=lbmdone-xblock`, edx-sga → 待核实（sed，Batch 1）
- **状态**: 逐个验证阶段闭合。详见 `py36-git-layer-probe-20260723.md`

## 4. ipaddr — 自动消解

- **用量**: `embargo/models.py` + `embargo/forms.py`（2 文件）
- **状态**: embargo 正被 DCC #2322 移除（APPROVED）
- **动作**: #2322 merge 后 ipaddr 用量归零。**不单列工作**。

## 5. beautifulsoup — 伪成本

- **现状**: bs3 仅被 `pynliner` transitive dep 引用，0 个 platform 源文件直接 import 旧 bs3
- **已用 bs4**: 4 个文件
- **动作**: `base.txt` pin 改 `beautifulsoup4==4.9.3`（~1 行改），不产生代码改动

---

## 汇总

> ⚠️ 估时: best-case（SAML 不用 + coursegraph 移除）→ **+2-3d**。若 prod 用 SAML + coursegraph 需替换 → **+4-6d**。

| # | 项目 | 阻塞 Py3? | 工作 | 估时 |
|---|------|:---:|------|------|
| 1 | coursegraph/py2neo | 是 | **先查 prod 用量** → 移除(2-3d) 或 替换(1-2d) | 1-3d |
| 2 | SAML/dm.xmlsec | 是 | **先查 prod 用量** → 跳过(0d) 或 适配(1-2d) | 0-2d |
| 3 | lbmdone-xblock `importlib.resources` | 是 | backport 或升级（CMS GRADABLE_BLOCKS 运行时）| 0.5d |
| 4 | **django-cas Py3 兼容** | 否（skip） | **CAS feature-flagged off**（live `lms.env.json` `AUTH_USE_CAS` absent→False，Django 不 import）。**真跑 Py3 实测**: `__init__.py:22 iteritems` + `views.py:3 from urllib import urlencode` + urlparse/urllib/StringIO reorg 跨 6 文件（__init__/models/backends/views/middleware/tests），~0.5-1d。**但 CAS off → py3 env 直接从 py36-base.txt 删 pin（根因解），0d** | 0d（删 pin）/ 0.5-1d（若启用 CAS）|
| 5 | git 层其余（egg 修复等）| 否 | 3 auth 全过 + egg fix | 0.5d |
| 6 | ipaddr | 自动消解 | #2322 merge → 归零 | 0d |
| 7 | beautifulsoup | 否 | pin 改 bs4 | 0d |
| 8 | mysql-python | 是（Py2 only） | → mysqlclient（Batch 1） | 含在 ~2d |
| 9 | egg metadata 3 个 | 否（打包问题） | sed fix（Batch 1） | 含在 ~2d |
| **合计** | | | | **best-case +3-4d, 现实 +5-7d** |
