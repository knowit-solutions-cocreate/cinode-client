# cinode-client

A read-only Python library and CLI for the Cinode API, meant for agents first
and humans second.

- `docs/design.md` is the design. Read it before changing code.
- `docs/plan.md` is the roadmap and the task list for the current version.

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
  `docs/design.md`, `docs/plan.md`, `README.md` or this file out of date, fix
  them in the same PR. When a plan task is done, tick its checkboxes in
  `docs/plan.md` in that task's PR.
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

Live tests run only with credentials in the environment, never in CI:
`CINODE_LIVE_TESTS=1 uv run pytest -m live`.

## Workflow: orchestrated pull requests

Work on `docs/plan.md` is done by agents, one PR per task. The main session is
the **orchestrator**. Each agent it starts is told which role it has, and
follows that role's section below.

All agents act as the same GitHub user, so GitHub's "approve" and "request
changes" are not available. Every PR comment an agent posts starts with its
role in bold, for example `**Reviewer (spec)**`.

### The loop, per task

1. The orchestrator starts an **implementer** for the next unticked task.
2. The implementer opens a PR and reports back with its URL.
3. The orchestrator starts both **reviewers** at once, in parallel.
4. The orchestrator **triages** every finding: accept or reject, each with a
   one-line reason. It posts the triage as a PR comment.
5. If any finding was accepted, the orchestrator starts a **fixer** with the
   accepted items. When the fixer has pushed, go back to step 3 for a new round.
   The reviewers then check the fixes and review the new commits.
6. Once a round has no accepted blocking or should-fix findings and CI is
   green, the orchestrator squash-merges:
   `gh pr merge <n> --squash --delete-branch`.
7. The orchestrator pulls `main`, then goes on to the next task.

**Limits:** at most three review rounds per PR. If a PR is not clean after the
third, the orchestrator stops and asks the human.

**The orchestrator stops and asks the human when:**
- a task cannot be done as the plan describes it
- the design itself needs to change
- live tests need credentials that are not in the environment
- reviewers disagree on something that cannot be settled from the design

### Roles

Every agent prompt begins: *"You are the **<role>** agent in the cinode-client
workflow. Read `CLAUDE.md` (Rules and your role's section),
`docs/design.md`, and your task in `docs/plan.md`."* The prompt then gives the
task number, PR number or findings as needed.

#### Orchestrator

This is the main session. It plans, delegates, triages and merges. **It does
not write product code.**

- Starts every implementer and fixer in its own worktree (the Agent tool's
  worktree isolation).
- Triage has two parts:
  - Accept a finding when the design or plan backs it, or when it is a real
    defect.
  - Reject a finding that is out of scope, contradicts the design, or is only a
    matter of taste. Nits are optional.
- Keeps the human informed with one line per step: PR opened, review round N,
  merged.

#### Implementer

Carries out one plan task.

- Starts from `origin/main` on a branch named `task-NN-short-name`, and runs
  `uv sync`.
- Follows the task in `docs/plan.md`, and writes the tests it lists. It adds
  no others.
- Keeps within the task's files and interfaces. It may fix a small mistake in
  the plan, but must say so in the PR.
- Runs the four checks, commits in logical chunks, ticks the task's checkboxes
  in `docs/plan.md`, and pushes.
- Opens the PR with `gh pr create --base main`. The PR is titled
  `Task NN: <name>`, and its body gives:
  - what was built
  - any departure from the plan, and why
  - the output of the checks, summarised
- Replies with the PR URL and a summary of up to five lines.

#### Reviewer (spec)

Checks the PR against `docs/design.md` and the task in `docs/plan.md`.

- Checks:
  - Is every item in the task done?
  - Do the names, signatures and output shapes match the design?
  - Are the review-focus tests present?
  - Were the docs updated alongside the code?
  - Is anything in the PR beyond the task's scope?
- Does not change code. It may check out the branch and run the checks.
- Posts one comment with `gh pr review <n> --comment` that starts with
  `**Reviewer (spec)**`. Each finding is numbered, carries a severity
  (`blocking`, `should-fix` or `nit`) and gives a `file:line` reference.
  If there are no findings, the comment says `No findings.`
- Replies with the findings, or with "no findings".

#### Reviewer (code)

Checks the PR as a senior Python reviewer would.

- Checks:
  - correctness and edge cases
  - error handling
  - test design: do the tests pin behaviour, or only the implementation?
    It flags tests that exist for their own sake, and slow tests. It asks
    for a new test only when there is a real defect to pin.
  - typing
  - readability
  - needless complexity
- Also looks for any path that could send a request other than GET, and for
  real personnel data.
- Does not change code, and posts and replies exactly as the spec reviewer
  does, starting its comment with `**Reviewer (code)**`.

#### Fixer

Applies the findings the orchestrator accepted, and nothing else.

- Checks out the PR's branch in its own worktree and runs `uv sync`.
- Fixes each accepted finding. Adds a test only when the finding is a defect
  that a test can pin.
- Runs the four checks, commits in logical chunks and pushes to the same branch.
- Posts a PR comment starting with `**Fixer**` that lists each finding number
  and what was done about it.
- Replies with a short summary.
