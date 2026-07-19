# Browser Automation (Playwright) Guide

> Mac M5 + OrbStack + Hawthorn devstack  
> Date: 2026-07-19

---

## 1. Setup

```bash
pip3 install playwright
```

Chrome/chromium is already available on macOS — Playwright uses the system Chrome via channel option.

---

## 2. Architecture

```
Host (macOS)
├── Playwright Python library
├── System Chrome (headless or headful)
│
├── HTTP → Studio  0.0.0.0:18010
│                   ↑ Docker port mapping
│              edx.devstack.studio container
```

Playwright runs on the HOST, driving the Studio running inside Docker. This avoids installing a browser inside containers.

---

## 3. Core Workflow

### 3.1 Login

```python
page.goto('http://0.0.0.0:18010/signin')
page.fill('input[name="email"]', 'studio_admin@example.com')
page.fill('input[name="password"]', 'edx')
page.click('button[type="submit"]')
```

### 3.2 Create Course

Studio uses Backbone.js with modal dialogs. Key gotchas:

- "New Course" is an icon `<i class="new-course-button">`, not a text link
- Use `force=True` on clicks when element is obscured
- Must press Enter (not click) to submit the form
- Navigate via URL path (`/settings/advanced`) for course config

```python
# Navigate home, click New Course icon
page.goto(f"{BASE}/home/")
page.click('.new-course-button', force=True)

# Fill form
page.fill('#new-course-name', "Course Name")
page.fill('#new-course-number', "COURSE101")
page.fill('#new-course-run', "2026")
page.press('#new-course-run', 'Enter')  # Submit
```

### 3.3 Enable Advanced Modules

After course creation, navigate to advanced settings and set modules:

```python
page.goto(f"{BASE}/{course_id}/settings/advanced")
page.evaluate("""
    var el = document.querySelector('#advance-module-keys');
    if (el) { el.value = JSON.stringify(arguments[0]); }
""", advanced_modules_list)
```

### 3.4 Debug Mode

```python
browser = p.chromium.launch(headless=False, channel='chrome')
```

Shows browser window; useful for debugging selectors and visual confirmation.

---

## 4. Automation Script: create_test_courses.py

Location: `scripts/create_test_courses.py`

### Usage

```bash
cd devstack
python3 scripts/create_test_courses.py            # headless
python3 scripts/create_test_courses.py --headed    # show browser
python3 scripts/create_test_courses.py --dry-run   # login only, no creation
```

### Creates

| Course | Number | Type |
|--------|--------|------|
| XBlock Component Test | XBlock101 | All components |
| Poll Component Test | POLL101 | Poll XBlock |
| ILT Course Test | ILT101 | ILT XBlock |
| PDF Component Test | PDF101 | PDF XBlock |
| SCORM Course Test | SCORM101 | SCORM XBlock |

Each course auto-enables 36 advanced modules.

---

## 5. Playwright API Patterns

### Selectors

```python
# CSS
page.click('.class-name')
page.fill('#input-id', 'text')

# Text content
page.get_by_text("Submit", exact=True)

# Force click (bypass pointer-interception)
page.locator('.button').click(force=True)
```

### Navigation

```python
page.goto(url, timeout=5000)              # navigate
page.go_back()                             # back
page.wait_for_timeout(1000)               # pause for JS render
page.wait_for_selector('.element')         # wait for element
```

### JS Execution

```python
# Get value
csrf = page.evaluate("document.querySelector('[name=csrfmiddlewaretoken]').value")

# Async fetch
resp = page.evaluate("""(async () => {
    const r = await fetch('/api/endpoint/', {...});
    return await r.json();
})()""")
```

### Event Capture

```python
# JS console errors
page.on("console", lambda msg: print(msg.text) if msg.type == "error" else None)

# Uncaught exceptions
page.on("pageerror", lambda err: print(err))
```

---

## 6. Test Configuration

| Test User | Password |
|-----------|----------|
| `studio_admin@example.com` | `edx` |
| `edx@example.com` | `edx` |
| `instructor@example.com` | `edx` |

See `docs/test-data.md` for full user list.

---

## 7. Troubleshooting

| Issue | Fix |
|-------|-----|
| Click not working | Use `force=True` or `page.evaluate("el.click()")` |
| Login redirects back | Wait longer after submit: `page.wait_for_timeout(3000)` |
| CSRF token null | Page might not have loaded; add `page.wait_for_timeout(1000)` before query |
| `SyntaxError: Illegal return statement` in evaluate | Wrap async code in `(async () => { ... })()` |
| Page stuck loading | Use shorter timeout; many Ajax calls never "complete" |
| Backbone.js elements not interactive | Use `page.press()` or `page.evaluate()` instead of `.click()` |
