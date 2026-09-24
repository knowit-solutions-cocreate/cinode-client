# cinode-client

A read-only Python library and CLI for the Cinode API, meant for agents first
and humans second.

- `docs/design.md` is the design. Read it before changing code.
- `docs/plan.md` is the task list for the version in progress.
- `docs/roadmap.md` lists the versions; `docs/plans/` holds the plans of
  released versions.

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
- **Plans are per version, and archived at release.** `docs/plan.md` holds
  the plan for the version in progress, and `docs/roadmap.md` lists the
  versions, one line each. When a version is released, its plan moves
  unchanged to `docs/plans/v<major>.<minor>.md` with `git mv`, so that
  `git log --follow` keeps its history, and `docs/plan.md` becomes a stub
  or the next version's plan. An archived plan is frozen: only its links may
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

Live tests run only with credentials in the environment, never in CI:
`CINODE_LIVE_TESTS=1 uv run pytest -m live`.

## Workflow: orchestrated pull requests

Each version is built in two phases, each in its own session:

1. **Design.** The **designer** works with the human to decide what the
   version is, and writes the design changes and the plan. This is the only
   phase in which the human is at the keyboard.
2. **Build.** The **orchestrator** carries out the plan unattended: one PR per
   task, written, reviewed and fixed by agents. It stops only at the points
   listed in *Human in the loop*.

Each agent a session starts is told which role it has, and follows that role's
section below.

All agents act as the same GitHub user, so GitHub's "approve" and "request
changes" are not available. Every PR comment an agent posts starts with its
role in bold, for example `**Reviewer (spec)**`.

### Starting a version

When `docs/plan.md` has no open tasks, no version is in progress. The human
starts a **designer** session:

> You are the designer for cinode-client. Read `CLAUDE.md`, then follow
> *Starting a version*. We are planning the next roadmap entry.

The designer then:

1. **Reads everything into context:** `CLAUDE.md`, `docs/design.md`,
   `docs/roadmap.md`, the archived plans in `docs/plans/`, `CHANGELOG.md`,
   the code, and open issues and PR threads where relevant. It arrives knowing
   the system, rather than rediscovering it through questions.
2. **Frames the version with the human.** It proposes a scope from the roadmap
   and a list of open questions, then settles them with the human one decision
   at a time. It recommends an answer for each question, but the human decides.
3. **Runs feedback loops** where they help, and brings real decisions back to
   the human:
   - An **explorer** probes the live API for areas the version touches.
   - A **critic** reads the draft design and plan as a hostile reviewer.
     The critic always runs at least once, on the complete draft.
4. **Writes the handoff:** the changes to `docs/design.md`, a new
   `docs/plan.md` in the format of the archived plans (goal, constraints,
   review focus, file map, tasks with interfaces), and the roadmap entry. These
   go in as one PR.
5. **Waits for the human to approve and merge that PR.** That approval is the
   handoff.
6. **Retires,** with exactly: *"My work here is done, I retire."* It starts no
   orchestrator and does nothing further in that session.

The human then starts a fresh **orchestrator** session:

> You are the orchestrator for cinode-client. Read `CLAUDE.md` and run the
> plan in `docs/plan.md`.

#### Sizing tasks

Aim for bite-sized tasks, but not tiny ones. Every task carries a fixed
overhead: an implementer, two reviewers, a triage and often a fixer and a
second round. In v0.1 that came to roughly 200–300k agent tokens and 10–15
minutes a task, however small the change. A good task:

- delivers one coherent piece (a module and its listed tests, or a group of
  CLI commands) that a reviewer can judge on its own
- folds scaffolding, configuration and docs into the task that needs them,
  instead of making them tasks of their own
- is split only where a reviewer could reasonably reject one half and accept
  the other
- stays within one PR a reviewer can hold in mind; in v0.1 the transport,
  about 200 lines and its tests, was the upper end, and took three rounds

### The loop, per task

1. The orchestrator starts an **implementer** for the next unticked task.
2. The implementer opens a PR and reports back with its URL.
3. The orchestrator starts the **reviewers**. In round 1 it starts both, in
   parallel. From round 2 onwards it starts only the **code reviewer**, and
   checks for itself that the fixes match the triage and that the docs and PR
   description are current.
4. The orchestrator **triages** every finding: accept or reject, each with a
   one-line reason. It posts the triage as a PR comment.
5. If any finding was accepted, the orchestrator starts a **fixer** with the
   accepted items. When the fixer has pushed, go back to step 3 for a new round.
   The code reviewer then checks the fixes and reviews the new commits.
6. Once a round has no accepted blocking or should-fix findings and CI is
   green, the orchestrator squash-merges:
   `gh pr merge <n> --squash --delete-branch`.
7. The orchestrator pulls `main`, then goes on to the next task. After the
   last task it stops for the release (see *Human in the loop*).

**Limits:** at most three review rounds per PR.

### Human in the loop

These are the only points at which work waits for the human. Everywhere else,
agents decide and carry on.

**Design phase** (the human is present throughout):
1. Every scope and design decision.
2. Approving and merging the handoff PR (design changes and plan).

**Build phase** (the orchestrator stops, says why in one line, and waits):
3. **Release.** When the last task is merged, the orchestrator reports that
   the plan is done. Tagging, building and publishing a release waits for the
   human.
4. **The design needs to change**, beyond fixing wording.
5. **A task cannot be done as the plan describes it.**
6. **A PR is still not clean after three review rounds.**
7. **Reviewers disagree** on something the design cannot settle.
8. **Credentials or access are missing**, or were rejected.
9. **Anything outward-facing beyond PRs and merges to `main`:** repository
   settings, publishing, deleting branches or tags other than a merged PR's
   own branch, or anything that cannot be undone.

The orchestrator never works around a stop, for example by weakening a test
or narrowing a task to get past it.

### Working agreements

What the loop has taught so far. These apply to every agent, whatever its role.
When the orchestrator notices a cheaper or safer way of working, it adds it
here right away, in a small docs PR.

- **Short replies.** An agent replies to the orchestrator in at most three
  lines: the PR URL or head SHA, the finding count or what changed, and any
  departure. The details belong in the PR description or comment, not in the
  reply, which keeps the orchestrator's context small.
- **The spec reviewer runs once, on Sonnet.** In Tasks 1–9 the spec reviewer's
  value was in round 1 (API shape, drift between code and docs); in later
  rounds it found almost nothing. It runs in round 1 only, with the Sonnet
  model, since it is checklist work against the design and plan. The code
  reviewer runs every round on the session's model.
- **Rounds after the first review only the delta.** Reviewers read the triage
  and Fixer comments, check the accepted items, review only the new commit
  range, and do not re-raise rejected findings.
- **Fixers work on a local branch.** The PR branch is usually still checked
  out in the implementer's worktree, so a fixer runs
  `git switch -c fix-prN origin/<branch>` and pushes with
  `git push origin HEAD:<branch>`.
- **The PR description tracks the code.** Whoever changes behaviour updates
  the PR description in the same step: the implementer when opening the PR,
  the fixer when a fix changes what the description says. A stale description
  becomes the squash commit's message.
- **The orchestrator fixes trivial nits itself.** A stale PR description or a
  one-line docs wording fix is done by the orchestrator directly (in a scratch
  worktree, never on `main`), instead of costing a fixer and another round.
- **Carry context forward.** The orchestrator's prompt to each implementer
  names the merged tasks, the patterns they established (helpers, validators,
  guards) and any follow-up a review left for this task.
- **Every agent starts in its own worktree, reviewers included.** Twice a
  reviewer whose working directory was the main checkout moved its `HEAD` by
  accident. The orchestrator starts reviewers with worktree isolation too, so
  a slip lands in a throwaway worktree. A reviewer reviews in that worktree,
  with `git switch --detach origin/<branch>`, and makes no second one: the
  sandbox blocks commands in a worktree outside the agent's own.
- **Leave nothing running.** Agents stop every process they start before
  replying. `ls` may be aliased to something slow, so they use `command ls`.
- **Keep shared space clean.** Agents name scratch files and worktrees
  uniquely (for example with the PR number and role), never overwrite files
  they did not create, and remove their own worktrees when done. The
  orchestrator removes the finished agent worktrees after each merge.
- **Interrupted agents.** If the machine sleeps or an agent dies mid-step,
  its results are on GitHub (PR, comment, push). The orchestrator checks what
  was actually posted or pushed, and restarts only what is missing.
- **Credentials.** Agents push over SSH using the key configured for Claude in
  the environment (`GIT_SSH_COMMAND`). They never change git or SSH
  configuration.

### Resuming

The orchestrator keeps no state of its own; the repository holds it. To pick
up after a break or a lost context:

1. Pull `main`. The first task in `docs/plan.md` with unticked boxes is next.
   If `docs/plan.md` has no open tasks, no version is in progress, and the
   next step is a designer session, which the human starts (see *Starting a
   version*).
2. Run `gh pr list`. If that task already has an open PR, read its comments to
   see which round it is in and what was last triaged. Carry on from there.

### Roles

Every agent prompt begins: *"You are the **<role>** agent in the cinode-client
workflow. Read `CLAUDE.md` (Rules and your role's section),
`docs/design.md`, and your task in `docs/plan.md`."* The prompt then gives the
task number, PR number or findings as needed.

#### Designer

The main session of the design phase. It decides the version with the human,
writes the design changes and the plan, and hands off. **It writes no product
code and starts no implementer.**

- Follows *Starting a version*.
- Starts explorers and critics with worktree isolation, and gives each the
  draft or the question in its prompt.
- Keeps decisions with the human. It recommends, but does not choose scope on
  the human's behalf.
- Ends the session with exactly: *"My work here is done, I retire."*

#### Explorer

Answers the designer's questions about the live API.

- Read-only: GET requests only, through the `cinode` CLI or the library where
  they cover it, otherwise `curl` with the environment's credentials.
- Reports response shapes, nullability, permissions (which calls return 403
  for this account) and pagination, with field names and types only.
- **Never quotes personnel data.** Values are replaced by their type, for
  example `"firstName": <string>`, and it reports counts, not lists.
- Replies in at most ten lines, since its findings shape the design.

#### Critic

Reads the draft design and plan as a hostile reviewer, before the handoff.

- Looks for:
  - gaps (requirements with no task, tasks with no test for their risk)
  - contradictions between the design and the plan
  - scope creep
  - tasks that are too small to carry their overhead, or too big to review
    as one PR
  - interfaces a later task depends on that no earlier task produces
  - anything in the plan that would make an unattended orchestrator stop
    unnecessarily
- Writes its findings to the designer, numbered with severity, not to a PR.
- Replies in at most ten lines.

#### Orchestrator

The main session of the build phase. It delegates, triages and merges.
**It does not write product code, and it does not redesign.** A needed
design change is a stop (see *Human in the loop*).

- Starts every agent (implementers, fixers and reviewers) in its own worktree,
  using the Agent tool's worktree isolation.
- Triage has two parts:
  - Accept a finding when the design or plan backs it, or when it is a real
    defect.
  - Reject a finding that is out of scope, contradicts the design, or is only a
    matter of taste. Nits are optional.
- Keeps the human informed with one line per step: PR opened, review round N,
  merged.
- Adds each new lesson to *Working agreements* as soon as it is learnt.

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
- Replies as *Working agreements* describe: at most three lines.

#### Reviewer (spec)

Checks the PR against `docs/design.md` and the task in `docs/plan.md`.

- Checks:
  - Is every item in the task done?
  - Do the names, signatures and output shapes match the design?
  - Are the review-focus tests present?
  - Were the docs updated alongside the code?
  - Is anything in the PR beyond the task's scope?
- Does not change code. It may check out the branch and run the checks.
- Reviews in its own worktree, detached at the PR head, and never checks out
  or modifies the main checkout.
- Posts one comment with `gh pr review <n> --comment` that starts with
  `**Reviewer (spec)**`. Each finding is numbered, carries a severity
  (`blocking`, `should-fix` or `nit`) and gives a `file:line` reference.
  If there are no findings, the comment says `No findings.`
- Replies in at most three lines: the finding count, and one line for each
  finding that is not a nit.

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
- Reviews in its own worktree, detached at the PR head, and never checks out
  or modifies the main checkout.
- Does not change code, and posts and replies exactly as the spec reviewer
  does, starting its comment with `**Reviewer (code)**`.

#### Fixer

Applies the findings the orchestrator accepted, and nothing else.

- Checks out the PR's branch in its own worktree and runs `uv sync`.
- Fixes each accepted finding. Adds a test only when the finding is a defect
  that a test can pin.
- Runs the four checks, commits in logical chunks and pushes to the same branch.
- Posts a PR comment starting with `**Fixer**` that lists each finding number
  and what was done about it, and updates the PR description if a fix changed
  what it says.
- Replies in at most three lines: the old and new head SHA, and what changed.
