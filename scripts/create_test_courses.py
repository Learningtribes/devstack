#!/usr/bin/env python3
"""Automated test course creator for Hawthorn devstack Studio.
Uses Playwright with system Chrome.

Usage:
    python3 scripts/create_test_courses.py             # headless (default)
    python3 scripts/create_test_courses.py --headed     # show browser
    python3 scripts/create_test_courses.py --dry-run    # login only, no creation
"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE = "http://0.0.0.0:18010"
EMAIL = "studio_admin@example.com"
PASSWORD = "edx"

COURSES = [
    {"name": "XBlock Component Test", "number": "XBlock101", "run": "2026"},
    {"name": "ILT Course Test", "number": "ILT101", "run": "2026"},
    {"name": "SCORM Course Test", "number": "SCORM101", "run": "2026"},
    {"name": "PDF Component Test", "number": "PDF101", "run": "2026"},
    {"name": "Poll Component Test", "number": "POLL101", "run": "2026"},
]


def login(page):
    print("[login]", end=" ", flush=True)
    page.goto(f"{BASE}/signin", timeout=5000)
    page.fill('input[name="email"]', EMAIL)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3000)
    print("OK")


def create_course(page, name, number, run):
    print(f"[create] {name} ({number}) ...", end=" ", flush=True)
    
    # Navigate to home first to reset state
    page.goto(f"{BASE}/home/", timeout=5000)
    page.wait_for_timeout(1000)
    
    # Click New Course icon (force to bypass overlays)
    page.click('.new-course-button', force=True, timeout=5000)
    page.wait_for_timeout(1500)
    
    # Fill form
    page.fill('#new-course-name', name)
    page.fill('#new-course-number', number)
    page.fill('#new-course-run', run)
    page.wait_for_timeout(500)
    
    # Submit with Enter
    page.locator('#new-course-run').press('Enter')
    page.wait_for_timeout(4000)
    
    # Check if navigated to course outline (URL has course+org+number+run)
    if 'course-v1' in page.url:
        course_key = page.url.split('/')[-1]
        print(f"OK -> {course_key}", end=" ", flush=True)
        if enable_advanced_modules(page, course_key):
            print("[advanced modules saved]")
        else:
            print("[WARN: advanced modules NOT saved]")
        return True
    else:
        print(f"FAIL (url)")
        return False


ADVANCED_MODULES = [
    "poll", "survey", "scormxblock", "pdf", "ilt",
    "drag-and-drop-v2", "google-document", "google-calendar",
    "done", "lbmdonexblock", "iframe", "externality",
    "openassessment", "word_cloud", "audio", "animation",
]


def enable_advanced_modules(page, course_key):
    """Persist the advanced-modules list via Studio's REST API.

    Setting the CodeMirror textarea value alone does NOT save — Studio persists
    advanced settings through a POST to the model endpoint. We drive that endpoint
    directly (with the page's CSRF token) so the change is actually stored.
    """
    settings_url = "{}/settings/advanced/{}".format(BASE, course_key)
    page.goto(settings_url, timeout=8000)
    page.wait_for_timeout(1500)

    result = page.evaluate(
        """async ([url, modules]) => {
            const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
            const token = tokenEl ? tokenEl.value
                : (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
            if (!token) return {ok: false, error: 'no csrf token'};
            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRFToken': token,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    advanced_modules: {value: modules},
                }),
            });
            return {ok: resp.ok, status: resp.status};
        }""",
        [settings_url, ADVANCED_MODULES],
    )
    return bool(result and result.get("ok"))


def main():
    headed = "--headed" in sys.argv
    dry_run = "--dry-run" in sys.argv
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed,
            channel="chrome",
            args=["--no-sandbox", "--disable-gpu"]
        )
        page = browser.new_page()
        
        try:
            login(page)
            
            if dry_run:
                print("[dry-run] Skipping course creation")
                return
            
            created = 0
            failed = 0
            for c in COURSES:
                if create_course(page, c["name"], c["number"], c["run"]):
                    created += 1
                else:
                    failed += 1
            
            print(f"\nDone: {created} created, {failed} failed")
            
        except Exception as e:
            print(f"\nERROR: {e}")
            if not headed:
                page.screenshot(path="/tmp/course_creation_error.png")
                print("Screenshot: /tmp/course_creation_error.png")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
