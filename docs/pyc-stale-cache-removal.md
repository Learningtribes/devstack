# `.pyc` Stale Cache After Module Removal

> Reusable lesson from PR #2357 CMS test failures. Also affects any module removal PR (embargo, badges, support, etc.).

---

## Symptom

After deleting `.py` source files from a removed Django app, test suites crash with:

```
RuntimeError: Model class <app>.models.<Model> doesn't declare an explicit
app_label and isn't in an application in INSTALLED_APPS.
```

Alternatively: `ImportError` for modules that "shouldn't exist" because source files were deleted but `.pyc` bytecode remains.

## Root Cause

Python's import system checks for `.pyc` files when `.py` sources are absent. If the compiled bytecode still exists in the directory, Python imports it — and Django tries to register models from a module no longer in `INSTALLED_APPS`.

This is particularly dangerous in devstack containers where:
- The container's filesystem survives across `git checkout` operations
- `paver`'s `clean_test_files` step only cleans `*.pyc` in the project root, not subdirectories
- `__pycache__/` directories accumulate across multiple Python version runs

## Detection

Check for orphan `.pyc` files in removed module directories:

```bash
# After switching to a branch that removes a module
find openedx/core/djangoapps/<removed_app>/ -name '*.pyc' -o -name '__pycache__'
```

Also check inside Docker containers if the devstack mounts the platform directory:

```bash
docker exec edx.devstack.lms find /edx/app/edxapp/edx-platform/openedx/core/djangoapps/<removed_app>/ -name '*.pyc'
```

## Fix

### Host-side (if bind-mounted)

```bash
find <removed_app_dir>/ -name '*.pyc' -delete
find <removed_app_dir>/ -name '__pycache__' -type d -exec rm -rf {} +
```

### Container-side

```bash
docker exec edx.devstack.lms find /edx/app/edxapp/edx-platform/<removed_app_dir>/ -name '*.pyc' -delete
docker exec edx.devstack.studio find /edx/app/edxapp/edx-platform/<removed_app_dir>/ -name '*.pyc' -delete
```

## Prevention

### 1. Add to `paver clean_test_files`

The existing paver clean step runs:
```bash
find . -name '.git' -prune -o -name '*.pyc' -exec rm {} \;
```

This cleans the entire project, but only when `clean_test_files` actually runs. In devstack, `.pyc` files can persist between manual test runs outside paver.

### 2. Git hook

Consider a post-checkout hook that cleans `.pyc` from removed app directories. See `module-removal-analysis` skill "Deployment Checklist" for the full removal pipeline.

### 3. `.gitignore` is not enough

`.pyc` files are already in `.gitignore`, but `.gitignore` only prevents tracking — it doesn't delete existing files. Git's `clean -fdX` would work but also removes other ignored artifacts.

## Affected Modules (M4 removal)

| Module | Directory | `.pyc` risk |
|--------|----------|:---:|
| embargo | `openedx/core/djangoapps/embargo/` | ✅ Confirmed (#2357) |
| badges | `lms/djangoapps/badges/` | ⚠️ Potential |
| support | `lms/djangoapps/support/` | ⚠️ Potential |
| zendesk_proxy | `openedx/core/djangoapps/zendesk_proxy/` | ⚠️ Potential |
| external_auth | `common/djangoapps/external_auth/` | ⚠️ Potential |
| entitlements | `common/djangoapps/entitlements/` | ⚠️ Potential |

## Quick Check Command

```bash
# Check all known removed module directories for stale .pyc
for dir in \
  openedx/core/djangoapps/embargo \
  lms/djangoapps/badges \
  lms/djangoapps/support \
  openedx/core/djangoapps/zendesk_proxy \
  common/djangoapps/external_auth \
  common/djangoapps/entitlements; do
  count=$(find /Users/noahwang/workspace/hawthorn/platform/$dir -name '*.pyc' 2>/dev/null | wc -l)
  [ "$count" -gt 0 ] && echo "⚠️  $dir: $count .pyc files"
done
echo "Done."
```
