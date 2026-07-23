# 「抄答案」— 上游 Juniper Py3 模式对照挖掘

> Date: 2026-07-23
> Source: `upstream/open-release/juniper.master` (`de946f3cca`) vs 我们的 Hawthorn fork
> Method: 对每种高风险模式，找上游的实际 diff，对照我们的修复，提炼最佳实践

---

## 1. iteritems / itervalues / iterkeys

### 上游怎么做

上游**统一使用 `six.` 前缀**，且**不管 bracket notation 还是 dot notation 都包在 `six.` 函数调用里**：

```python
# 上游 split.py — bracket notation
for block_id, block in six.iteritems(course.structure['blocks'])

# 上游 split.py — method chain  
for key, value in six.iteritems(old_definition.get('fields', {}))

# 上游 mongo/base.py — dict literal
for key, value in six.iteritems({'org': 'org', 'course': 'course', 'run': 'name'})

# 上游 — 其他变体
six.viewkeys(bulk_write_record.structures)
six.iterkeys(defs_dict)
six.itervalues(new_module_data)
six.string_types  # 而非 basestring
```

### 我们怎么做

我们同样使用 `six.iteritems(expr)` 模式，但在自动化脚本中曾有两个正则 bug：
- `(\w+)\.iteritems()` → 匹配了 `_block_relations` 但保留了前面的 `self.` → `self.six.iteritems(...)` ❌
- `\S+\.iteritems()` → 匹配了 `'name'}` 等非标识符 → 产生 `{'run': six.iteritems('name'})` ❌

**结论**：我们的最终修复（`six.iteritems(expr)`）与上游完全一致。自动化脚本需注意：bracket notation `obj['key']`、method chain `fn().iteritems()`、dict literal `{...}.iteritems()` 都需要手动修复。

---

## 2. raise E, V, T → six.reraise()

### 上游怎么做

```python
# 上游 capa_base.py:297
six.reraise(Exception, Exception(msg), sys.exc_info()[2])
```

上游将 msg 字符串包装为 `Exception(msg)` 实例传入。

### 我们怎么做

```python
# 我们的 capa_base.py（phase5-6a-xmodule）
six.reraise(Exception, msg, sys.exc_info()[2])
```

我们直接传 msg 字符串。Py2 中 `raise E, "string", tb` 会自动调用 `E("string")` 创建实例，所以两种写法**行为等价**。但上游的显式包装更清晰。

**其他 raise 模式对照**：

| 原始 | 上游 | 我们 |
|------|------|------|
| `raise Exception(msg), None, tb` | `six.reraise(Exception, Exception(msg), tb)` | `six.reraise(Exception, msg, tb)` |
| `raise ProcessingError(msg), None, tb` | (同模式) | `six.reraise(ProcessingError, msg, tb)` |
| `raise ValueError(msg), None, tb` | (同模式) | `six.reraise(ValueError, msg, tb)` |

**结论**：一致，无需修正。

---

## 3. text_type / string_types

### 上游怎么做

```python
# 上游 student/models.py
from six import text_type
hasher.update(text_type(user.id).encode('utf8'))
log.warning(u"User %s failed to enroll in non-existent course %s", user.username, text_type(course_key))

# 上游 mongo/base.py — 显式 six.text_type()
six.text_type(self.course_id)
six.text_type(location)
isinstance(data, six.string_types)
if six.PY2:  # 极少用
    ...
```

### 我们怎么做

```python
from six import text_type
text_type(course_key)
text_type(err)
isinstance(value, string_types)  # from six import string_types
```

**结论**：完全一致。上游偶尔使用 `six.` 前缀的全限定名（`six.text_type()`），我们用 import 后的短名。直接 import 更简洁，上游的 `six.` 前缀在超大文件中可能只是为了避免与其他 import 冲突。

---

## 4. CSV 处理

### 上游怎么做

这是 OEP-7 标记为高风险的模式。上游有专门的 CSV 编码处理：

```python
# 上游 instructor_task/models.py
def _get_utf8_encoded_rows(self, rows):
    for row in rows:
        yield [six.text_type(item).encode('utf-8') for item in row]

csvwriter = csv.writer(output_buffer)
csvwriter.writerows(self._get_utf8_encoded_rows(rows))
```

**模式**：
1. 先 `six.text_type(item)` 确保是 text
2. 再 `.encode('utf-8')` 转 bytes
3. 传给 csv.writer（Py2 需要 bytes，Py3 需要 text — 但显式 encode 避免了平台差异）

### 我们怎么做

我们目前**尚未系统化处理 csv** — 6B 和 6A 批次的 csv 引用点没有专门的编码包装层。

**建议**：对 `csv.writer`/`csv.reader` 的调用点，参照上游模式添加显式的 `text_type` + `encode('utf-8')` 包装。在 celery bridge 就绪、Py3 测试回路建立后，这是第一批会暴露的 runtime 问题。

---

## 5. except E, e: → except E as e:

### 上游怎么做

上游在 Juniper 中已全面清除此模式（Juniper 是 Py3-only，`except E, e:` 是 SyntaxError）。具体处理：全部改为 `except E as e:`。

### 我们怎么做

同样改为 `as`。但脚本初次运行时遗漏了 17 处（xqueue_interface 2处 + symmath/formula/check 13处 + contentstore 1处 + loncapa 1处），由 CI 的 `py_compile` 捕获并修正。

**结论**：一致。遗漏原因是初始 grep 覆盖不全（sandbox-packages、symmath 子目录）。

---

## 6. unicode sandwich / bytes boundary

### 上游怎么做

上游在 Juniper 中有专门的 bytes/unicode 边界处理：

```python
# S3 upload — 显式转 bytes
# Upstream: instructor_task/models.py (commit 640e8cc9c8e)

# hashlib — 显式 encode
hashlib.sha1(text_type(course_id).encode('utf-8')).hexdigest()

# Django migrations — 显式 CharField 替代 TextField
# upstream: student/models.py (commit 897bd25b013)
```

### 我们怎么做

我们做了 `unicode()` → `text_type()` 的机械替换，但**未系统化处理 bytes/str 边界**（hashlib、boto/S3、csv、base64）。

**建议**：这是 OEP-7 "unicode sandwich"（入口 decode，出口 encode，内部纯 text）的核心。Py3 测试回路建立后优先排查的领域。

---

## 7. `__hash__` / `__cmp__` / total_ordering

### 上游怎么做

上游有专门的 cmp 修复 commit（`f5f875401aa`）。Juniper 迁移中处理了：
- `__cmp__` → `__eq__` + `__lt__`（或 `@functools.total_ordering`）
- `cmp()` 函数 → 自定义 key 函数
- `sort(cmp=...)` → `sort(key=...)`

### 我们怎么做

**尚未触及**。Phase 4/5 批次中未发现 `__cmp__` 或 `cmp()` 调用。但 Phase 5 部分模块（特别是 xmodule 的 sorting 逻辑）可能存在。

**建议**：用 `rg 'def __cmp__|cmp\(|sort\(cmp=' lms cms openedx common` 全树扫描，确认真无残留。

---

## 8. 上游做法 vs 我们做法 — 快速对照

| 模式 | 上游 Juniper | 我们 | 一致？ |
|------|------|------|:---:|
| `iteritems()` | `six.iteritems(dict)` | `six.iteritems(dict)` | ✅ |
| `itervalues()` | `six.itervalues(dict)` | `six.itervalues(dict)` | ✅ |
| `iterkeys()` | `six.iterkeys(dict)` | `six.iterkeys(dict)` | ✅ |
| `viewkeys()` | `six.viewkeys(dict)` | 未使用（我们用 `six.iterkeys`） | ⚠️ 等价 |
| `reraise` | `six.reraise(E, E(msg), tb)` | `six.reraise(E, msg, tb)` | ✅ 等价 |
| `text_type` | `six.text_type(x)` 或 `text_type(x)` | `text_type(x)` | ✅ |
| `string_types` | `six.string_types` 或 `string_types` | `string_types` | ✅ |
| `range` | `six.moves.range` | `six.moves.range` | ✅ |
| `urllib` | `six.moves.urllib.parse` | `six.moves.urllib.parse` | ✅ |
| CSV | 显式 encode 包装 | ⚠️ 未系统处理 | 🔴 差距 |
| base64 | 显式 bytes 处理 | ⚠️ 未系统处理 | 🟡 待查 |
| hashlib | `text_type(x).encode('utf-8')` | ⚠️ 部分处理 | 🟡 待查 |
| `__cmp__`/`cmp()` | 全移除 | ⚠️ 未扫描 | 🟡 待查 |

---

## 9. 行动建议

基于对照结果：

1. **CSV 包装**（P1）：扫描所有 `csv.writer`/`csv.reader` 调用点，参照上游 `_get_utf8_encoded_rows` 模式添加显式编码
2. **hashlib 审计**（P1）：扫描 `hashlib` + `update()` 调用，确认已 `encode('utf-8')`
3. **`__cmp__`/`cmp()` 扫描**（P2）：全树扫描确认无残留
4. **base64 审计**（P2）：扫描 `base64.b64encode`/`b64decode` 调用，确认传入的是 bytes
5. **继续使用 `six.iteritems()` 而非 `six.viewitems()`** — Py3 等价，上游在多个模块也用了 `six.iteritems`
