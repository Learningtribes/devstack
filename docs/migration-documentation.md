# Devstack Migration Documentation

> Status: REPOSITORY-LOCAL INDEX
> Authority: Devstack runtime assets, runbooks, and execution evidence
> Cross-project Hub:
> https://github.com/Learningtribes/platform/tree/migration_discussion/docs/migration_discussion
> Current migration state: follow the Hub README's current-status entry.

Devstack owns documentation coupled to its Docker, image, dependency,
runtime, wrapper, database, and browser-runner implementation. The migration
Hub owns cross-repository state, decisions, PR ordering, and active handoffs.

## Retain in Devstack

- Docker and Python runtime build/run documentation;
- backup, restore, fixture, and local-environment runbooks;
- PR browser/runtime verification results;
- execution-review evidence;
- scripts, compose files, requirements, and runtime settings; and
- raw evidence produced by Devstack commands.

## Historical Status Documents

Documents such as `progress-plan-20260724.md`,
`handoff-prompt-20260723.md`, `migration-inventory.md`,
`phase4-progress.md`, and `phase5-coverage-gap.md` are dated evidence.
Their embedded PR state and next actions are not current authority.

## Retained Untracked Documents

The protected `noah-py2-m-chip-master` worktree retains 17 untracked review,
handoff, and PR #2347 files. Their SHA256 inventory is prepared in the Hub
change at:

`docs/migration_discussion/evidence/devstack-retained-untracked-20260806.sha256`

The source files remain unmodified. `execution-review-16-20260723.md` requires
sensitive-term review before publication.

## Link Policy

- Repository-local execution instructions link to repository-local scripts and
  runbooks.
- Exact Platform integration evidence uses a branch-qualified Git object or
  GitHub branch URL.
- Cross-repository state and active assignments link to the migration Hub.
- Historical documents use past tense and identify their observation boundary.
