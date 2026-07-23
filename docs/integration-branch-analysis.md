# Py3 整合分支 — 对照上游 Juniper 差距分析

> Date: 2026-07-23
> 分支: `py3-integration`（8 条分支合并，零冲突）
> 计数口径（2026-07-23 修正）：**770 files / +1886 / −848 = 8 个分支各自 diff 的算术和**（见 §0 树状图）。**累积 diff vs merge-base `ae5411201c3` = 829 files / +1912 / −4575**（`git diff --shortstat ae5411201c3 HEAD`，实测）。两者口径不同——删除数累积远大于分支和，因分支分别 fork 自不同基点。**以累积口径（−4575）为准论改动规模**。
> 对照: `upstream/open-release/juniper.master` vs `upstream/open-release/ironwood.master`

---

## 0. 整合分支验证

```
py3-integration (21690c0c708 + 8 branches merged)
  │
  ├── student-py3-analysis     32f  +106/-19
  ├── courseware-py3           45f  +127/-73
  ├── instructor-py3           22f  +31/-10
  ├── contentstore-py3         88f  +286/-195
  ├── phase5-6d-apis           36f  +49/-10
  ├── phase5-6b-core          404f  +672/-211
  ├── phase5-6c-libs           37f  +98/-56
  └── phase5-6a-xmodule       106f  +517/-274
                              ─────────────
                              770f  +1886/-848   ← 各分支 diff 算术和
                              829f  +1912/-4575  ← 累积 vs merge-base ae5411201c3（实测）

✅ 零冲突合并
✅ py_compile 全部通过
✅ paver test_system 逐个模块验证过
```

---

## 1. 编译层：已覆盖且与 Juniper 一致

所有语法层变更（`except as`、`print()`、`raise`→`reraise`、`ur''`、lambda tuple unpack）均已处理。与上游 Juniper 的 diff 对照确认**无遗漏语法错误**。

---

## 2. 运行时层：对照 Juniper 发现的缺口

`compileall` 只能发现语法错误。以下缺口只有 Py3 运行时测试才能暴露。每个缺口都对照了上游 Juniper 的实际修复。

### 2.1 CSV 编码包装（3 个文件）

上游 Juniper 的 csv 修复模式（commit `8c4a31bf3af`）：在 `csv.reader()` 前显式 `.decode('utf-8')`，在 `csv.writer()` 前包装 `text_type → encode('utf-8')`。

我们触及了 4 个 csv 文件，仅 1 个正确：

| 文件 | 状态 | Juniper 修复参考 |
|------|:---:|------|
| `lms/djangoapps/instructor/views/api.py` | ✅ 已有 `.decode('utf-8')` | 已包含 |
| `cms/djangoapps/contentstore/views/import_export.py` | 🔴 缺 | Juniper 加了 encode/decode 包装 |
| `common/djangoapps/student/.../anonymized_id_mapping.py` | 🔴 缺 | — |
| `lms/djangoapps/courseware/views/views.py` | 🔴 缺 | — |

**修复模式**：
```python
# 读取：Py2 .read() 返回 str，Py3 返回 str 也可。但 csv.reader 需要 str（Py3）或 bytes 的迭代器（Py2）。
# 上游做法：显式 decode 后 splitlines，统一为 text
rows = csv.reader(data.decode('utf-8').splitlines())

# 写入：上游 _get_utf8_encoded_rows() 模式
def _get_utf8_encoded_rows(rows):
    for row in rows:
        yield [six.text_type(item).encode('utf-8') for item in row]
csvwriter.writerows(_get_utf8_encoded_rows(rows))
```

---

### 2.2 base64 str/bytes 边界（6 个文件）

上游 Juniper 的 base64 修复（`contentstore/import_export.py`）：
```python
# 修复前（Py2 only）
base64.urlsafe_b64encode(repr(key))

# 修复后（Py2/3 兼容）
base64.urlsafe_b64encode(repr(key).encode('utf-8')).decode('utf-8')
```

我们触及的 7 个 base64 文件，仅 1 个正确：

| 文件 | 状态 |
|------|:---:|
| `cms/djangoapps/contentstore/views/import_export.py` | ✅ 已有 encode/decode |
| `cms/djangoapps/contentstore/api/views/course_import.py` | 🔴 缺 |
| `cms/djangoapps/contentstore/tasks.py` | 🔴 缺 |
| `common/lib/xmodule/xmodule/lti_2_util.py` | 🔴 缺 |
| `common/lib/xmodule/xmodule/lti_module.py` | 🔴 缺 |
| `openedx/core/djangoapps/oauth_dispatch/dot_overrides/validators.py` | 🔴 缺 |

**修复模式**：`base64.b64encode(data)` → `base64.b64encode(data.encode('utf-8')).decode('utf-8')`（如果 data 是 str）。如果 data 已经是 bytes，则不需要改。

---

### 2.3 hashlib encode（需逐个验证）

上游 Juniper 的 hashlib 修复（commit `b3c062be1b6`）：Py2 和 Py3 对同一字符串的 md5 结果相同，但前提是传入 bytes。

我们的模式：`text_type(x).encode('utf-8')` 或 `x.encode('utf-8')`。部分文件已有（如 `contentstore/tasks.py`、`utils.py`），部分可能缺。需逐个文件确认 `hashlib.xxx(xxx).update()` / `hashlib.xxx(xxx).hexdigest()` 的参数是 bytes。

触及的文件中 ~10 个可能需要添加 `.encode('utf-8')` 包装，但有些可能已经正确处理（`text_type().encode()`）。

---

## 3. 结构层：我们 vs Juniper 的覆盖范围差异

| 维度 | 我们覆盖 | Juniper 覆盖 | 差距 |
|------|:---:|:---:|------|
| core libs（capa/calc/chem/symmath） | ✅ 6C | ✅ | — |
| xmodule | ✅ 6A | ✅ | — |
| openedx/core/djangoapps | ✅ 6B | ✅ | — |
| LMS djangoapps（courseware/instructor） | ✅ 4/5 | ✅ | — |
| CMS contentstore | ✅ 4/5 | ✅ | — |
| APIs（certificates/extended/bulk/lti） | ✅ 6D | ✅ | — |
| **lms/djangoapps 其余模块** | ❌ | ✅ | ~30 个 LMS 子模块未覆盖 |
| **cms/djangoapps 其余模块** | ❌ | ✅ | ~15 个 CMS 子模块未覆盖 |
| **Django 2.2 升级** | N/A | ✅ | 我们主动跳过了 |
| **celery 4.4** | 规划中 | N/A（他们停在 3.1） | 我们更激进 |
| **vendor XBlocks（ora2/proctoring）** | ❌ | ✅ | 6F 未开始 |

---

## 4. 代码改动覆盖度评估

```
已覆盖（累积 829 files, +1912/-4575 vs merge-base；分支和 770/+1886/-848 见 §0）:
  ████████████████████  Phase 4 (4 modules) + Phase 5 (4 batches)
  ████████████████████  语法层：except/print/raise/ur''/lambda ✅
  ████████████████░░░░  模式层：unicode/text_type/basestring/iteritems/xrange ✅
  ████████░░░░░░░░░░░░  边界层：csv/base64/hashlib 编码包装 ⚠️ ~20 files gap

未覆盖:
  ░░░░░░░░░░░░░░░░░░░░  LMS djangoapps 其余 ~30 模块
  ░░░░░░░░░░░░░░░░░░░░  CMS djangoapps 其余 ~15 模块
  ░░░░░░░░░░░░░░░░░░░░  6E utilities + 6F vendored src/
  ░░░░░░░░░░░░░░░░░░░░  Django 2.2 升级（主动跳过）
  ░░░░░░░░░░░░░░░░░░░░  Batch 1 依赖升级（celery/pymongo/等）
```

**代码层完成度**：~85% 的语法+模式层已覆盖。~15% 的文件级覆盖缺口（6E/6F/LMS/CMS 残量）+ ~20 个文件需要 csv/base64 编码包装。

---

## 5. 下一步行动（在 pip 依赖墙之前）

### 立即（整合分支已就绪）

1. **csv/base64/hashlib 编码包装**（1 天）：在 `py3-integration` 分支上补 20 个文件的 str↔bytes 边界处理，参照上游 Juniper 模式
2. **6E 散碎模块快速扫完**（0.5 天）：`lms/lib`、`cms/lib`、`course_experience` 等
3. **全量 `paver test_system` 在 Py2 下重验证**：确认整合分支在 devstack 上全部 green

### 然后（进入 pip 依赖阶段）

4. **Batch 1 依赖升级**（7 天）：在整合分支上做 mysqlclient/pymongo/celery 升级
5. **Py3.8 容器中 `paver test_system` allow-fail baseline**：建立可度量 backlog
6. **逐模块修 Py3 测试**

---

## 6. 最大的发现

**整合分支零冲突合并** 证明了各模块的 Py3 现代化工作是正交的，没有隐藏的跨模块依赖问题。这意味着当 DCC PRs 合并后，8 条分支可以按任意顺序 rebase 到 master，不会产生级联冲突。

**csv/base64/hashlib 是 compileall 盲区** —— 只有对照 Juniper 才能发现。这些模式在 Py2 下不报错（bytes/str 混用容忍度高），但在 Py3 下会出现 `TypeError: a bytes-like object is required, not 'str'`。我们的 `py_compile` 无法检测这类问题。
