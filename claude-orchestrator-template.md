# Orchestrated PR workflow

A portable template for running a project's plan as agent-written pull
requests. It is the workflow this repository was built with, generalised.
Copy it into a new project's `CLAUDE.md` and fill in the bracketed parts.

Each version is built in two phases, each in its own session:

1. **Design.** The **designer** works with the human to decide what the
   version is, and writes the design changes and the plan. This is the only
   phase in which the human is at the keyboard.
2. **Build.** The **orchestrator** carries out the plan unattended: one PR per
   task, written, reviewed and fixed by agents. It stops only at the points
   in *Human in the loop*.

Every agent a session starts is told which role it has and follows that
role's section below.

## Starting a version

When `docs/plan.md` has no open tasks, no version is in progress. The human
starts a **designer** session:

> You are the designer for [project]. Read `CLAUDE.md`, then follow
> *Starting a version*. We are planning the next roadmap entry.

The designer:

1. **Reads everything into context:** `CLAUDE.md`, the design, the roadmap,
   the archived plans, the CHANGELOG, the code, and open issues and PR
   threads where relevant.
2. **Frames the version with the human:** it proposes a scope and a list of
   open questions, then settles them one decision at a time. It recommends an
   answer for each, but the human decides.
3. **Runs feedback loops:** an **explorer** for external systems the version
   touches (such as a live API), and a **critic** on the complete draft, at
   least once.
4. **Writes the handoff:** the design changes, a new `docs/plan.md` (goal,
   constraints, review focus, file map, tasks with interfaces) and the
   roadmap entry, as one PR.
5. **Waits for the human to approve and merge it.** That is the handoff.
6. **Retires,** with exactly: *"My work here is done, I retire."*

The human then starts a fresh **orchestrator** session:

> You are the orchestrator for [project]. Read `CLAUDE.md` and run the plan in
> `docs/plan.md`.

**Sizing tasks.** Aim for bite-sized tasks, but not tiny ones: every task
carries a fixed overhead (an implementer, two reviewers, a triage, often a
fixer and a second round). A good task delivers one coherent piece a reviewer
can judge on its own, folds scaffolding, config and docs into the task that
needs them, and is split only where a reviewer could reject one half and
accept the other.

## Rules

- **Use worktrees and feature branches.** Every change is made in its own git
  worktree, on a branch cut from an up-to-date `origin/main`.
- **Never commit or push to `main`.** Changes reach `main` only as
  squash-merged pull requests.
- **Commit in logical chunks.** Each commit is one coherent step that passes
  the checks. Plain imperative messages, no prefixes, no emoji.
- **Update `CLAUDE.md` and the docs in the same change** that makes them
  stale. Tick a task's boxes in `docs/plan.md` in that task's PR.
- **Plans are per version, and archived at release.** `docs/plan.md` holds
  the plan for the version in progress, and `docs/roadmap.md` lists the
  versions, one line each. When a version is released, its plan moves
  unchanged to `docs/plans/v<major>.<minor>.md` with `git mv`, so that
  `git log --follow` keeps its history, and `docs/plan.md` becomes a stub
  or the next version's plan. An archived plan is frozen: only its links may
  be fixed. Before archiving, anything in the plan that is still true about
  the system moves to a living document (the design, the README or this file).
- **Few, fast tests.** A test exists only when it pins behaviour the design
  depends on, or behaviour that has already gone wrong. Never write one for
  coverage. The default run finishes in under [2] seconds: inject clocks,
  mock the network.
- **Sensitive data stays out** of the repo, PR descriptions and comments.
  Fixtures are synthetic. Summarise live output with counts. Test failure
  messages must never echo live output: bind a check to a variable, then
  assert.
- [Project rules: toolchain (e.g. "use uv for everything"), checks, invariants.]

**Checks** (every commit passes all of them):
[e.g. `uv run pytest` · `uv run ruff check` · `uv run ruff format --check` · `uv run pyright`]

## The loop, per task

1. The orchestrator starts an **implementer** for the next unticked task.
2. The implementer opens a PR and reports back.
3. **Round 1:** the orchestrator starts both reviewers in parallel, the
   **spec reviewer** on a mid-tier model (e.g. Sonnet) and the **code
   reviewer** on the session's model.
   **Round 2 onwards:** it starts only the code reviewer, and checks for
   itself that the fixes match the triage and that the docs and PR
   description are current.
4. The orchestrator **triages** every finding (accept or reject, with a
   one-line reason) and posts the triage as a PR comment.
5. If anything was accepted, it starts a **fixer** with the accepted items,
   then goes back to step 3.
6. When a round has no accepted blocking or should-fix findings and CI is
   green, the orchestrator squash-merges
   (`gh pr merge <n> --squash --delete-branch`), pulls `main`, removes the
   finished agent worktrees, and moves on. After the last task it stops for
   the release.

**Limits:** at most three review rounds per PR.

## Human in the loop

These are the only points at which work waits for the human.

**Design phase** (the human is present): every scope and design decision, and
approving and merging the handoff PR.

**Build phase** (the orchestrator stops, says why in one line, and waits):
1. **Release:** when the last task is merged. Tagging and publishing wait for
   the human.
2. **The design needs to change**, beyond fixing wording.
3. **A task cannot be done as the plan describes it.**
4. **A PR is still not clean after three review rounds.**
5. **Reviewers disagree** on something the design cannot settle.
6. **Credentials or access are missing**, or were rejected.
7. **Anything outward-facing beyond PRs and merges to `main`:** repository
   settings, publishing, deleting branches or tags other than a merged PR's
   own branch, or anything that cannot be undone.

The orchestrator never works around a stop, for example by weakening a test
or narrowing a task to get past it.

**Resuming:** the orchestrator keeps no state of its own. Pull `main`: the
first unticked task in `docs/plan.md` is next. `gh pr list` and the PR
comments show which round an open PR is in. If `docs/plan.md` has no open
tasks, no version is in progress; the next step is a designer session, which
the human starts.

## Working agreements

When the orchestrator notices a cheaper or safer way of working, it adds it
here right away, in a small docs PR.

- **Every agent starts in its own worktree, reviewers included** (Agent tool
  worktree isolation). An agent whose working directory is the main checkout
  will eventually move its `HEAD` by accident.
- **Short replies.** Agents reply to the orchestrator in at most three lines.
  Details go in the PR description or comment, which keeps the orchestrator's
  context small.
- **Later rounds review only the delta.** Reviewers read the triage and fixer
  comments, review only the new commit range, and don't raise rejected
  findings again.
- **Fixers work on a local branch.** The PR branch is usually still checked
  out in the implementer's worktree, so:
  `git switch -c fix-prN origin/<branch>`, then
  `git push origin HEAD:<branch>`.
- **The PR description tracks the code.** Whoever changes behaviour updates
  it. A stale description becomes the squash commit message.
- **The orchestrator fixes trivial nits itself** (a stale description, a
  one-line docs wording fix) in a scratch worktree, instead of costing a
  fixer and a round.
- **Carry context forward.** Each implementer prompt names the merged tasks,
  the patterns they established (helpers, validators, guards) and any
  follow-up a review left for this task.
- **Verify claims before acting on them.** Reviewers can be wrong. Check a
  surprising claim yourself before accepting or rejecting it.
- **Leave nothing running.** Agents stop every process they start before
  replying.
- **Keep shared space clean.** Name scratch files and worktrees uniquely,
  never overwrite files you didn't create, and remove your own worktrees.
- **Interrupted agents.** If one dies mid-step, check what actually reached
  GitHub and restart only what's missing.
- **Credentials.** Agents use what's in the environment and never change git,
  SSH or tool configuration.

## Roles

Every agent prompt begins: *"You are the **<role>** agent in the <project>
workflow. Read `CLAUDE.md` (Rules, Working agreements and your role's
section), `docs/design.md`, and your task in `docs/plan.md`."* All agents act
as the same GitHub user, so every PR comment starts with its role in bold,
e.g. `**Reviewer (code)**`. GitHub's approve and request-changes are not
used.

### Designer

The main session of the design phase. It decides the version with the human,
writes the design changes and the plan, and hands off. **It writes no product
code and starts no implementer.**

- Follows *Starting a version*, and keeps decisions with the human.
- Starts explorers and critics with worktree isolation.
- Ends the session with exactly: *"My work here is done, I retire."*

### Explorer

Answers the designer's questions about external systems (for example a live
API).

- Read-only. Reports shapes, nullability, permissions and pagination, as
  field names and types only.
- Never quotes sensitive data: values are replaced by their type, and it
  reports counts, not lists.
- Replies in at most ten lines.

### Critic

Reads the draft design and plan as a hostile reviewer, before the handoff.

- Looks for:
  - gaps and contradictions between the design and the plan
  - scope creep
  - tasks too small to carry their overhead, or too big for one PR
  - interfaces a later task needs that no earlier task produces
  - anything that would make an unattended orchestrator stop unnecessarily
- Reports numbered findings with severity to the designer.
- Replies in at most ten lines.

### Orchestrator

The main session of the build phase. It delegates, triages and merges.
**It does not write product code, and it does not redesign:** a needed design
change is a stop.

- Accept a finding when the design backs it or it is a real defect. Reject
  it when it's out of scope, contradicts the design, or is a matter of
  taste. Nits are optional.
- Posts one line per step for the human: PR opened, review round N, merged.
- Records each new lesson under *Working agreements*.

### Implementer

Carries out one plan task.

- Branches `task-NN-short-name` from `origin/main`, then sets up the
  environment.
- Writes only the tests the task lists, and stays within the task's files
  and interfaces. It may fix a small plan mistake, but says so in the PR.
- Runs the checks, commits in logical chunks, ticks the plan boxes, pushes,
  confirms CI is green.
- Opens the PR titled `Task NN: <name>`. The body covers what was built, any
  departure from the plan and why, and a summary of the checks.
- Reply (at most three lines): PR URL and head SHA, what was built, any
  departure.

### Reviewer (spec) (round 1 only, mid-tier model)

Checks the PR against the design and the task.

- Is every task item done? Do names, signatures and output shapes match the
  design? Are the listed tests present? Were the docs updated? Is anything
  out of scope?
- Posts one `gh pr review <n> --comment` headed `**Reviewer (spec)**`, with
  numbered findings, each with a severity (`blocking`, `should-fix` or
  `nit`) and a `file:line`, or `No findings.`
- Changes no code.
- Reply (at most three lines): the finding count, and one line per non-nit
  finding.

### Reviewer (code) (every round)

Reviews the PR as a senior engineer would.

- Covers correctness and edge cases, error handling, and test design (does
  it pin behaviour? flag tests that exist for their own sake, and slow ones;
  ask for a test only to pin a real defect), typing, readability and
  needless complexity. Also checks the project's invariants (e.g. read-only,
  no sensitive data).
- Probes claims with throwaway scripts and mocked I/O.
- Posts and replies like the spec reviewer, headed `**Reviewer (code)**`.
  Changes no code.

### Fixer

Applies the accepted findings, and nothing else.

- Follows the fixer branch recipe above. Adds a test only when a finding is
  a defect that a test can pin.
- Runs the checks, commits, pushes, and confirms CI is green. Updates the PR
  description if a fix changed what it says.
- Posts a `**Fixer**` comment listing each finding number and what was done
  about it.
- Reply (at most three lines): old and new head SHA, what changed.
