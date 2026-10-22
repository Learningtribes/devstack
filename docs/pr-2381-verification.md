# PR #2381 legacy dashboard Programs pages — Verification Results

> Date: 2026-09-09 (re-run after review cleanup)
> PR: #2381 DCC — remove standalone `/dashboard/programs/` + ProgramDetails stack
> Branch: `dcc-legacy-dashboard-programs-removal` (worktree `platform-dcc-legacy-dashboard-programs-removal`)
> Head: `0ab34145dbde8856da4bf38a85da5392d4f378e4` + uncommitted review cleanup (urls include dropped, orphan utils/Sass/PO)
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2381.yml` — **6 surfaces** (2 discriminators, 4 gates)

---

## 1. PR Summary

81 files, +39/−4,909. Two different "programs" surfaces:

| Layer | Change |
|-------|--------|
| DELETE | Standalone listing/details: `/dashboard/programs/`, `/dashboard/programs/<uuid>/`, fragment URL siblings. Review cleanup deleted `learner_dashboard/urls.py` and dropped the `lms/urls.py` include. |
| KEEP | `ProgramsFragmentView` still renders the dashboard Learning Paths fragment (`my_programs`) |
| KEEP | Navbar `reverse('my_training_programs')` instead of `program_listing_view` |

The two page views were `@login_required` on master (unconditional registration, no feature-flag gate on the URL include). Unauthenticated GET 302s to `/login` → Playwright follows to 200. PR: no child routes → 404. Real route-existence flip.

---

## 2. Results

### 2026-09-09 — dcc-legacy-dashboard-programs-removal (review cleanup) — 6/6 passed (14.1s)

Local destack, `PLATFORM_MOUNT=platform-dcc-legacy-dashboard-programs-removal`. HEAD `0ab34145dbd` plus uncommitted cleanup: `learner_dashboard/urls.py` deleted, `include('learner_dashboard.urls')` dropped, orphan `utils.py` / Sass / msgid `"Programs"` removed. Same 6 surfaces; no `paver update_assets`.

| # | Surface | Result | Role |
|---|---------|:---:|------|
| 1 | `GET /dashboard/programs/` (`request: true`, `auth: none`) → 404 | ✅ | **discriminator** |
| 2 | `GET /dashboard/programs/00000000-0000-0000-0000-000000000000/` (`request: true`, `auth: none`) → 404 | ✅ | **discriminator** |
| 3 | LMS `/` → 200 | ✅ | gate |
| 4 | `/dashboard` → 200 | ✅ | gate (KEEP fragment) |
| 5 | `/my_training_programs/` (`request: true`, `auth: qacert`) → 200 | ✅ | gate (KEEP) |
| 6 | Studio `/home/` → 200 | ✅ | gate |

Master baseline not re-run: assertions were not retargeted (still unauthenticated 404 vs login-followed 200). 2026-09-04 master run remains the discriminator control.

### 2026-09-04 — dcc-legacy-dashboard-programs-removal — 6/6 passed (12.0s)

Local destack, `PLATFORM_MOUNT=platform-dcc-legacy-dashboard-programs-removal`, HEAD `0ab34145dbd`.

| # | Surface | Result | Role |
|---|---------|:---:|------|
| 1 | `GET /dashboard/programs/` (`request: true`, `auth: none`) → 404 | ✅ | **discriminator** |
| 2 | `GET /dashboard/programs/00000000-0000-0000-0000-000000000000/` (`request: true`, `auth: none`) → 404 | ✅ | **discriminator** |
| 3 | LMS `/` → 200 | ✅ | gate |
| 4 | `/dashboard` → 200 | ✅ | gate (KEEP fragment) |
| 5 | `/my_training_programs/` (`request: true`, `auth: qacert`) → 200 | ✅ | gate (KEEP) |
| 6 | Studio `/home/` → 200 | ✅ | gate |

### 2026-09-04 — master baseline — 2 failed / 4 passed (19.6s)

Master worktree `platform` at `dde48ce4592` (`#2389` GoodHabitz; Programs pages still present). Same checklist.

| # | Surface | Master | PR | Role |
|---|---------|:---:|:---:|------|
| 1 | `/dashboard/programs/` | ❌ 200 (login 302 followed) | ✅ 404 | **discriminator** |
| 2 | `/dashboard/programs/<dummy-uuid>/` | ❌ 200 (login 302 followed) | ✅ 404 | **discriminator** |
| 3 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 4 | `/dashboard` | ✅ 200 | ✅ 200 | gate |
| 5 | `/my_training_programs/` | ✅ 200 | ✅ 200 | gate (KEEP) |
| 6 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |

---

## 3. Discriminators

Both are compile-independent HTTP status flips. No `paver update_assets`, no program fixture, no dummy UUID lookup.

`@login_required` fires before the view body, so a dummy UUID is enough for the details route. Unauthenticated `request: true` so Playwright does not mangle the path and follows the master 302 to `/login` → 200.

These surfaces are listed **first** (`auth: none`). The runner shares one `BrowserContext`; a later `auth: none` still carries `qacert` cookies and would 200 the listing on master — vacuous.

---

## 4. Gates

| Surface | Verifies |
|---------|----------|
| LMS `/` | No import error after emptying `learner_dashboard.urls` and deleting the details stack |
| `/dashboard` | KEEP `ProgramsFragmentView.render_to_fragment` still called from `student.views.dashboard` |
| `/my_training_programs/` 200 | KEEP replacement page is still routed. Navbar now `reverse()`s this name |
| Studio `/home/` | CMS unaffected |

---

## 5. Vacuous / excluded

| Candidate | Why skipped |
|-----------|-------------|
| `/dashboard/programs_fragment/` | `EdxFragmentView` is not `login_required`; disabled `ProgramsApiConfig` or missing data 404s on master too |
| `/dashboard/programs/<uuid>/details_fragment/` | Same as fragment listing |
| Navbar "Programs" → "Learning Paths" | Gated on `show_program_listing` (`ProgramsApiConfig.enabled`). Off → both branches omit the tab |
| `/programs/<uuid>/about` | Marketing page, not touched |

---

## 6. Issues encountered

**Port 18000.** `financial-data-ingestion-hub-local-pg-api-1` was bound to `127.0.0.1:18000`. Stopped for the run; LMS/Studio stopped afterward; that container restarted.

**Heartbeat 503.** 2026-09-09 LMS boot returned 503 until `edx.devstack.elasticsearch` was started (modulestore + SQL were already OK). Checklist surfaces do not need ES; started only to clear the enable-script heartbeat gate.

**Shared Playwright cookie jar.** `auth: none` after `qacert` is not anonymous. Discriminators listed first.

**egg_info.** Fresh worktree lacked `Open_edX.egg-info`; regenerated inside the LMS container before enable.

---

## 7. Run History

| Run | Date | Branch | Result | Note |
|:---:|------|--------|:---:|------|
| 1 | 2026-09-04 | dcc-legacy-dashboard-programs-removal | **6/6** | First PR run (emptied urls.py, include still present) |
| 2 | 2026-09-04 | master | **2 discriminators** | listing + details 200≠404; 4 gates passed |
| 3 | 2026-09-09 | dcc-legacy-dashboard-programs-removal | **6/6** | After review cleanup: urls.py deleted, include dropped |

---

## 8. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2381.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-dcc-legacy-dashboard-programs-removal` |
| Setup | `DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn` `PLATFORM_MOUNT=.../platform-dcc-legacy-dashboard-programs-removal` `docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio` |

---

## 9. Setup / teardown

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-dcc-legacy-dashboard-programs-removal
docker stop financial-data-ingestion-hub-local-pg-api-1   # frees :18000
cd "$DEVSTACK_WORKSPACE/devstack"
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio
docker exec edx.devstack.lms bash -lc 'source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && python setup.py egg_info && for d in common/lib/*/; do (cd "$d" && python setup.py egg_info); done'
# enable + provision from the skill dir, then:
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 CHECKLIST_PR=pr-2381 npm run checklist
```

After the master baseline, LMS/Studio were stopped, harness `devstack_docker.py` blocks reverted in both worktrees, and the financial-hub container was started again.
