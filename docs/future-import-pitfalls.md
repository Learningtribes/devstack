# `__future__` Import Pitfalls in Py3 Migration

> Reusable lessons from PR #2357 student Py3 migration. The three `__future__` imports have different risk profiles in Py2.7 — only two are safe for blind application.

---

## Safe: `absolute_import, division, print_function`

These three are safe to add to any Py2.7 file:

| Import | Effect in Py2.7 | Risk |
|--------|-----------------|:---:|
| `absolute_import` | Makes `import foo` absolute (PEP 328) | ⚠️ Breaks implicit relative imports in packages |
| `division` | `/` becomes true division (PEP 238) | ✅ Low — test suite catches semantic changes |
| `print_function` | `print` becomes a function (PEP 3105) | ✅ Low — `print` statement becomes `SyntaxError` |

### `absolute_import` — the implicit relative import trap

Adding `absolute_import` to a package's `__init__.py` or module changes ALL bare `from <name> import ...` statements from implicit-relative to absolute. This breaks sibling imports:

```python
# In student/views/__init__.py — BREAKS with absolute_import
from admin_panel import *    # Python looks for top-level 'admin_panel', not '.admin_panel'

# Fix: explicit relative import
from .admin_panel import *
```

**Detection pattern**: `grep -r '^from [a-z]' <package_dir>/` in files with `absolute_import`. Any bare import that looks like a local module name (lowercase start, no dots) is suspicious.

**Affected in #2357**: `student/views/__init__.py` — 5 implicit imports (`admin_panel`, `dashboard`, `login`, `management`, `session_invitation_pdf`).

---

## Dangerous: `unicode_literals`

**Do NOT add `unicode_literals` to existing Py2.7 code without test updates.**

| Import | Effect in Py2.7 | Risk |
|--------|-----------------|:---:|
| `unicode_literals` | All string literals become `unicode` (PEP 3112) | 🔴 High — changes `repr()`, `type()`, C extension interactions |

### Concrete failures in #2357

Adding `unicode_literals` to 31 student files caused 11 test failures across 3 areas:

1. **Tuple `repr()` mismatch** (7 tests): `render_to_response('template.html', [])` — the template name becomes unicode, so the tuple repr is `(u'template.html', [])` instead of `('template.html', [])`. Tests comparing string representations broke.

2. **Mock call argument mismatch** (4 tests): `email_user("('emails/subject.txt', ...)")` — the template tuple is `repr()`'d into the email body, and `unicode_literals` adds `u''` prefixes throughout.

3. **JSON response mismatch** (2 tests): `json.dumps` of values that contain unicode tuples.

### When `unicode_literals` IS appropriate

- New code files (never existed without it)
- Files where ALL tests are updated to expect unicode
- Code that already uses `u''` prefixes everywhere

### Remediation

For existing Py3 migration batches, **remove `unicode_literals`** from the `__future__` import, keeping the other three. It can be added in a separate, test-aware pass.

```diff
-from __future__ import absolute_import, division, print_function, unicode_literals
+from __future__ import absolute_import, division, print_function
```

---

## Quick Audit Command

```bash
# Find files with unicode_literals in a module
grep -rl 'unicode_literals' common/djangoapps/<module>/ --include='*.py' | grep -v migrations | grep -v tests

# Find potential implicit relative imports broken by absolute_import
grep -r '^from [a-z][a-z_]* import' common/djangoapps/<module>/ --include='*.py'
```

---

## Summary

| Import | Add blindly? | Risk | Mitigation |
|--------|:---:|:---:|------|
| `absolute_import` | ⚠️ Check first | Implicit relative imports | `grep` for bare `from <local> import` |
| `division` | ✅ Yes | Semantic: `3/2` → `1.5` | Test suite catches |
| `print_function` | ✅ Yes | `SyntaxError` if `print` used as statement | `compileall` catches |
| `unicode_literals` | 🔴 No | `repr()`, `type()`, C extensions | Remove from batch, add later with test updates |
