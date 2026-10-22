# PR #2348 External Auth + Entitlements Removal - Verification Results

> Date: 2026-08-10
> PR: #2348 `refactor(m4.4-A): remove external_auth and entitlements`
> Target: `m4-4a-external-auth-entitlements` at `4801623685bfbec5be7504895c5f6cc840cb5e03`
> Baseline: detached worktree at `04a9ba0739e2bde6ea1a53ba3fbd568d564cc149`
> Runner: Playwright/Chromium checklist-as-code against local Hawthorn devstack

---

## 1. Scope

The PR removes `openedx/core/djangoapps/external_auth/` and
`common/djangoapps/entitlements/`, plus their settings, URLs, support UI,
learner Dashboard integration, assets, tests, and dependencies.

- 176 files changed
- 244 insertions
- 13,138 deletions
- Checklist: `checklists/pr-2348.yml` (5 discriminators, 5 gates)
- Interaction spec: `tests/external_auth_entitlements_flow.spec.ts`

Both branches ran with identical temporary settings:

```python
FEATURES['AUTH_USE_OPENID_PROVIDER'] = True
FEATURES['RESTRICT_ENROLL_BY_REG_METHOD'] = True
```

These settings make the two external-auth routes resolvable on the baseline,
preventing false-positive 404 assertions.

## 2. Checklist Results

### Target - 10/10 passed

| Surface | Target | Role |
|---|---:|---|
| Entitlement API | 404 | discriminator |
| Entitlement support tool | 404 | discriminator |
| Support index entitlement entry | absent | discriminator |
| OpenID provider XRDS | 404 | discriminator |
| Course-specific login | 404 | discriminator |
| Standard login | 200 | gate |
| Standard registration | 200 | gate |
| Learner Dashboard with real enrollment | card rendered | gate |
| LMS home | 200 | gate |
| Studio home | 200 | gate |

The final target rerun passed all surfaces; LMS home timed out once and passed
its configured retry. An earlier clean target run passed 10/10 in 9.6 seconds.

### Exact baseline - 5 expected failures, 5 passes (17.7s)

| Surface | Baseline | Expected target assertion | Control result |
|---|---:|---:|---|
| Entitlement API | 200 | 404 | failed as required |
| Entitlement support tool | 500, route resolved | 404 | failed as required |
| Support index entitlement entry | present | absent | failed as required |
| OpenID provider XRDS | 200 | 404 | failed as required |
| Course-specific login | 200 | 404 | failed as required |
| Standard login | 200 | 200 | passed |
| Standard registration | 200 | 200 | passed |
| Learner Dashboard | card rendered | card rendered | passed |
| LMS home | 200 | 200 | passed |
| Studio home | 200 | 200 | passed |

Every removal discriminator passes only on the PR and fails on the exact
baseline. All five surviving-flow gates pass on both revisions.

The baseline entitlement support route returned 500 because the shared static
output was built for the target and no longer contained the
`EntitlementSupportPage` webpack bundle. This remains a valid route-existence
control: baseline resolves and executes the support view (non-404), while the
target removes the route and returns 404. The independent support-index text
check also proves that the entitlement support entry existed on the baseline.

## 3. Real User Flow

Target-only interaction test: **1/1 passed in 13.3s**.

The test used disposable user `qam42348flow` and exercised:

1. `/register` with a real registration POST (200)
2. A new browser context and password login POST (200)
3. Course About page for `course-v1:edX+dc001+2026-07`
4. Real `POST /change_enrollment` (200)
5. Redirect to the course page
6. Dashboard rendering of the `Demo Course 001` enrollment card
7. Full-page Dashboard screenshot and browser diagnostics attachment

The standard registration, password authentication, enrollment, and Dashboard
paths therefore continue to work after removal of both modules.

## 4. Diagnostics and Static Checks

- Target and baseline LMS heartbeat: 200
- Target and baseline Studio sign-in/home: 200
- No unexpected Playwright page errors or failed requests in the successful
  interaction run
- Existing Triboo Dashboard `dsSwiper` error was retained in diagnostics as a
  known environment error; it is unrelated to this PR
- Removed-app import scan found no runtime imports of either deleted package
- `git diff --check` passed

## 5. Result

**PASS - no browser-acceptance blocker found.**

The target removes all five tested external-auth/entitlement surfaces, the
exact baseline proves those assertions are non-vacuous, and the standard learner
workflow plus LMS/Studio startup gates remain operational.

## 6. Artifacts

| Artifact | Location |
|---|---|
| Checklist | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2348.yml` |
| Interaction spec | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/tests/external_auth_entitlements_flow.spec.ts` |
