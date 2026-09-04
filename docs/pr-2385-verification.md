# PR #2385 teams SPLIT — Verification Results

> Date: 2026-09-04
> PR: #2385 M4.4-B teams SPLIT (Course Teams removed; ProgramAccessRole relocated)
> Branch: `teams-split` (worktree `platform-teams-split`)
> Head: `41b0a67a62b0d17ee4a66b5873deb9287f8b9438`
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2385.yml` — **6 surfaces** (2 discriminators, 4 gates)

---

## 1. PR Summary

146 files, +253/−14,540. Two different "teams" features:

| Layer | Change |
|-------|--------|
| DELETE | LMS Course Teams (`lms/djangoapps/teams/`): `/api/team/v0/*`, `/courses/{id}/teams/`, TeamsTab entry point |
| KEEP | `ProgramAccessRole` + Studio program-team UI moved to `lms/djangoapps/program_enrollments/` |
| CMS | `cms/urls.py` imports `ProgramTeamMembers` / `ProgramDetail` from the new module; `/api/team/` include retargeted |
| Tabs | `teams` added to `CourseTabList.REMOVED_TAB_TYPES` |

LMS Course Teams URLs were gated on `FEATURES['ENABLE_TEAMS']` (**default True** in `lms/envs/common.py`), so they are registered on master. That is a real route-existence flip, unlike `FEATURES['EMBARGO']` default False.

---

## 2. Results

### 2026-09-04 — teams-split — 6/6 passed (5.1s)

Local devstack, `PLATFORM_MOUNT=platform-teams-split`, HEAD `41b0a67a62b`.

| # | Surface | Result | Role |
|---|---------|:---:|------|
| 1 | `GET /courses/{course_key}/teams/` (`request: true`, `auth: none`) → 404 | ✅ | **discriminator** |
| 2 | `GET /api/team/v0/teams/` (`request: true`, `auth: qacert`) → 404 | ✅ | **discriminator** |
| 3 | LMS `/` → 200 | ✅ | gate |
| 4 | `/dashboard` → 200 | ✅ | gate |
| 5 | Studio `/home/` → 200 | ✅ | gate |
| 6 | Studio `/program_team/` (`request: true`, `auth: qastaff`) → 403 | ✅ | gate (KEEP) |

### 2026-09-04 — master baseline — 2 failed / 4 passed (7.6s)

Master worktree `platform` at `d089556570d` (behind 1 = `#2389` GoodHabitz; Course Teams still present). Same checklist.

| # | Surface | Master | teams-split | Role |
|---|---------|:---:|:---:|------|
| 1 | `/courses/{course_key}/teams/` | ❌ 200 (login 302 followed) | ✅ 404 | **discriminator** |
| 2 | `/api/team/v0/teams/` | ❌ 400 (`course_id must be provided`) | ✅ 404 | **discriminator** |
| 3 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 4 | `/dashboard` | ✅ 200 | ✅ 200 | gate |
| 5 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |
| 6 | Studio `/program_team/` | ✅ 403 | ✅ 403 | gate (KEEP) |

---

## 3. Discriminators

Both are compile-independent HTTP status flips. No `paver update_assets`, no teams fixture, no `course.teams_enabled` Mongo data.

**Dashboard route.** Unauthenticated `request: true` so Playwright does not mangle `+` in the opaque course key. Master `login_required` 302 is followed to `/login` → 200. PR: include gone → 404.

This surface is listed **first** in the YAML. The runner shares one `BrowserContext`; a later `auth: none` still carries `qacert` cookies. With those cookies master hits `TeamsDashboardView`, which 404s on the QA fixture course (`teams_enabled` off) — vacuous. Reordering made the master run fail 200≠404.

**Course Teams API.** Authenticated GET with no `course_id`: master returns 400 from `TeamsListView`; PR returns 404 because `/api/team/` is unregistered. Avoids `has_team_api_access` 403 on a course without teams.

---

## 4. Gates

| Surface | Verifies |
|---------|----------|
| LMS `/`, `/dashboard` | No import error after deleting `lms.djangoapps.teams` and the TeamsTab entry point |
| Studio `/home/` | CMS boots with the relocated `program_enrollments` imports |
| Studio `/program_team/` 403 | KEEP view is still routed. `qastaff` passes `studio_login_required`; without a program UUID the view returns 403 (`STUDIO_EDIT_CONTENT`). 404 would mean the KEEP page was dropped |

---

## 5. Vacuous / excluded

| Candidate | Why skipped |
|-----------|-------------|
| `/triboo-guanli/teams/courseteam/` | `CourseTeam` has no `admin.py` |
| Instructor roster "team" column | Needs `course.teams_enabled` |
| Course tab "Teams" | Plugin + stored tab; `REMOVED_TAB_TYPES` is deserialize-only |
| CMS `/api/team/v0/programadmins/` without id | List view reads `kwargs['id']` → 500 on cold Studio (observed flake) |

---

## 6. Issues encountered

**Port 18000.** `financial-data-ingestion-hub-local-pg-api-1` was bound to `127.0.0.1:18000`. Stopped for the run; LMS/Studio stopped afterward; that container restarted.

**Shared Playwright cookie jar.** `auth: none` after `qacert` is not anonymous. Dashboard discriminator had to be the first surface.

**KEEP `/program_team/`.** Unauthenticated 302; `qacert` 403; `qastaff` 403. Assert 403 with `qastaff` (same group as Studio home).

**egg_info.** Fresh worktree lacked `Open_edX.egg-info`; regenerated inside the LMS container before enable.

---

## 7. Run History

| Run | Date | Branch | Result | Note |
|:---:|------|--------|:---:|------|
| 1 | 2026-09-04 | teams-split | 5 passed, 1 flaky | KEEP API `/programadmins/` 500 then 403 |
| 2 | 2026-09-04 | teams-split | 5 passed, 1 flaky | KEEP `/program_team/` with `auth: none` after `qacert` → 403 then 200 |
| 3 | 2026-09-04 | teams-split | **6/6** | KEEP moved to `qastaff` 403 |
| 4 | 2026-09-04 | master | 1 discriminator | Dashboard still `auth: none` after `qacert` → vacuous 404 |
| 5 | 2026-09-04 | master | **2 discriminators** | Dashboard listed first; 200 vs 404 and 400 vs 404 |

---

## 8. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2385.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-teams-split` |
| Setup | `DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn` `PLATFORM_MOUNT=.../platform-teams-split` `docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio` |

---

## 9. Setup / teardown

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-teams-split
docker stop financial-data-ingestion-hub-local-pg-api-1   # frees :18000
cd "$DEVSTACK_WORKSPACE/devstack"
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio
docker exec edx.devstack.lms bash -lc 'source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && python setup.py egg_info && for d in common/lib/*/; do (cd "$d" && python setup.py egg_info); done'
# enable + provision from the skill dir, then:
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 CHECKLIST_PR=pr-2385 npm run checklist
```

After the master baseline, LMS/Studio were stopped, harness `devstack_docker.py` blocks reverted in both worktrees, and the financial-hub container was started again.
