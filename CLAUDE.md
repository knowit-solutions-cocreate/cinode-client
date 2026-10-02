# cinode-client

A read-only Python library and CLI for the Cinode API, meant for agents first
and humans second.

- `docs/design.md` is the design. Read it before changing code.
- `docs/plan.md` is the task list for the version in progress.
- `docs/roadmap.md` lists the versions; `docs/plans/` holds the plans of
  released versions.
- [`WORKFLOW.md`](WORKFLOW.md) is how the work gets done: the design and
  build phases, the roles, and the working agreements. Every agent reads it.

Repository: https://github.com/knowit-solutions-cocreate/cinode-client. It is
**public**.

## Rules

- **Use uv for everything:** `uv sync`, `uv add`, `uv run …`. Never use pip, and
  never activate a venv by hand.
- **Use worktrees and feature branches.** Every change is made in its own git
  worktree, on a branch cut from an up-to-date `origin/main`.
- **Never commit or push to `main`.** Changes reach `main` only as squash-merged
  pull requests.
- **Commit in logical chunks.** Each commit is one coherent step that passes
  the checks below. Messages are plain imperative sentences, with no prefixes
  and no emoji.
- **Update `CLAUDE.md` and the docs in the same change.** When a change makes
  `docs/design.md`, `docs/plan.md`, `README.md`, `WORKFLOW.md` or this file
  out of date, fix them in the same PR. When a plan task is done, tick its
  checkboxes in `docs/plan.md` in that task's PR.
- **Plans are per version, and archived at release.** `docs/plan.md` holds
  the plan for the version in progress, and `docs/roadmap.md` lists the
  versions, one line each. When a version is released, its plan moves
  unchanged to `docs/plans/v<major>.<minor>.md` with `git mv`, so that
  `git log --follow` keeps its history, and `docs/plan.md` becomes a stub
  or the next version's plan. `scripts/release.py prepare` makes these
  edits (see *Releasing* in `WORKFLOW.md`); it adds only the archive banner
  to the plan, and fixes its relative links. An archived plan is frozen: only its links may
  be fixed. Before archiving, anything in the plan that is still true about
  the system moves to a living document (the design, the README or this file).
- **Few, fast tests.** Write a test only when it pins behaviour the design
  depends on, or behaviour that has already gone wrong. Never write one for
  coverage. The default run must finish in **under two seconds**: inject
  clocks instead of sleeping, and mock the network with `respx`.
- **Read-only.** Never add an HTTP method other than GET, not behind a flag and
  not for a test.
- **Personnel data stays out of the repo, and out of PRs and comments.** Test
  fixtures are synthetic. Never paste live API output (names, emails, skill
  levels) into a commit, PR description or review comment. Summarise it
  instead ("50 members, 6 skipped").

### Checks

Every commit passes all four, and `pytest` reports under 2 s:

```
uv run pytest
uv run ruff check
uv run ruff format --check
uv run pyright
```

Live tests run only with credentials, never in CI:
`CINODE_LIVE_TESTS=1 uv run pytest -m live`. They may take credentials from
the credentials file, but the `cinode init` round trip needs them in the
environment and is skipped otherwise.
