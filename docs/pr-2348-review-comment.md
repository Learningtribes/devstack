## Browser Acceptance Testing - Verified

Tested PR #2348 at `4801623685bfbec5be7504895c5f6cc840cb5e03`
against the exact baseline `04a9ba0739e2bde6ea1a53ba3fbd568d564cc149`
with the same Playwright checklist and devstack feature settings.

### Removal discriminators

| Surface | PR | Baseline |
|---|---:|---:|
| Entitlement API | 404 | 200 |
| Entitlement support route | 404 | non-404 (view resolved) |
| Entitlement entry on support index | absent | present |
| OpenID provider XRDS | 404 | 200 |
| Course-specific login | 404 | 200 |

All five removal assertions pass only on the PR and fail on the baseline.

### Regression gates

- Standard login: 200 on both revisions
- Standard registration: 200 on both revisions
- Learner Dashboard: real enrollment card rendered on both revisions
- LMS home: 200 on both revisions
- Studio home: 200 on both revisions
- Real target flow: registration -> new-context password login -> About-page
  enrollment -> course page -> Dashboard card passed in 13.3s

Residual-reference scanning found no runtime imports of the deleted
`external_auth` or `entitlements` packages, and `git diff --check` passed.

No browser-acceptance blocker found. The removal behavior is proven by the
baseline control and the standard authentication/enrollment workflow survives.

Full evidence: `devstack/docs/pr-2348-verification.md`
