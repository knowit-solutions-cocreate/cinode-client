# cinode-client — plan for v0.2

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to carry out the tasks in order. Write only the
> tests a task lists; they pin behaviour the design depends on. Do not add
> tests for coverage. Steps use checkboxes for tracking.

**Goal:** v0.2 adds user profiles and resumes to the library and the CLI, as
lean, typed projections of Cinode's very large payloads.

**Architecture:** no new layers. Two model modules join `cinode.models`
(`profiles.py`, `resumes.py`), two sub-resources join `Users` (`UserProfile`,
`UserResumes`), `cinode.ops` gains `team_profiles`, and the CLI gains
`users profile`, `users resumes` and `teams profiles`.
Everything follows the v0.1 patterns: `CinodeModel` with `.raw`,
`Resource._one` and `._list`, `require_id`, `run()` in the CLI.

**Tech stack:** unchanged from v0.1. No new dependencies.

**Spec:** [`docs/design.md`](design.md), in particular *Profiles and resumes*
under *The API, as verified*, and the *Profile* and *Resumes* model sections.
Read them before starting; this plan does not repeat them.

## Global constraints

- Everything in v0.1's global constraints still holds: GET only, synthetic
  fixtures (company 99, user 1001, names like "Ada Example"), the four checks
  on every commit, the default run under two seconds, and only the tests
  listed.
- **Nothing changes that v0.1 shipped.** Existing names, signatures and output
  shapes stay. The work adds attributes to `Users`, exports to
  `cinode.models` and `cinode.ops`, commands to `cinode users` and
  `cinode teams`, and names to `cinode schema`.
- **Fixtures are small.** A synthetic profile or resume payload has one or two
  elements per section and a few of the keys v0.2 leaves out, enough to show
  that they are dropped. Never copy a live payload, even anonymised.
- **Live tests never show live text.** Profiles and resumes are free text about
  a person. Follow the pattern in `tests/live/test_acceptance.py`: bind each
  check to a name before asserting, and never put output in a message. Live
  tests read only the owner's data, whose profile has no employers or
  training; the unit fixture is what covers those sections.

## Review focus

Failure modes the design implies but does not spell out. Each one has a test
in the task named.

1. **The lean projection stays lean.** A dumped `Profile` has no `skills`,
   `references`, `extSkills` or `commitments` key, and a work experience's
   skills dump as `{keyword_id, name}` only. A dumped `Resume` has no template
   settings and no named block copies. Otherwise an agent gets hundreds of
   kilobytes it did not ask for. *(Tasks 1, 2)*
2. **Translations are passed through, not flattened or padded.** An element
   with two entries dumps both, each with its `language`; an element with one
   entry, in a two-translation profile, dumps one. `""` stays `""`.
   *(Task 1)*
3. **Seven fractional digits, no timezone.** `"2026-01-02T03:04:05.1234567"`
   parses to a naive `datetime` with microseconds `123456`, not an
   `UnexpectedResponseError`. *(Task 1)*
4. **Open shapes in resume blocks.** A string `blockId`, an unknown
   `blockType`, a block with inline texts and no `data`, and a `data: null`
   all parse. *(Task 2)*
5. **The spec is wrong about resume content.** `resumes.get` reads
   `resumes/{id}` and takes the blocks from `resume.blocks`. It never calls
   `resumes/{id}/dynamic`, which returns 404. *(Task 3)*
6. **A bad resume id is refused before any request.** `True`, `0` and `"5"`
   raise `ValueError`, as for every other id. *(Task 3)*
7. **`team_skills` does not change** when its loop moves to `ops/_members.py`.
   Its existing tests in `tests/test_ops.py` and `tests/cli/test_cli.py` pass
   unedited. *(Task 4)*

## File map

```
src/cinode/
  models/     profiles.py (new)  resumes.py (new)  skills.py  __init__.py
  resources/  users.py
  ops/        _members.py (new)  team_profiles.py (new)  team_skills.py  __init__.py
  cli/        users.py  teams.py  schema.py  _output.py (ResumeIdArg)
tests/
  support.py            profile_payload, resume_summary_payload, resume_payload
  test_models.py  test_resources.py  test_ops.py
  cli/test_cli.py  live/test_acceptance.py
README.md  CHANGELOG.md
```

---

### Task 1: Profile models

**Files:** `src/cinode/models/profiles.py`, `models/skills.py`,
`models/__init__.py`, `tests/support.py` (`profile_payload`),
`tests/test_models.py`.

**Produces:**
- In `models/profiles.py`, the models of the design's *Profile* section:
  - `Profile`, `Presentation`, `WorkExperience`, `Education`,
    `ProfileLanguage`, `Employer`, `Training` and `SkillRef`
  - the text entries `PresentationText`, `WorkExperienceText`,
    `EducationText`, `EmployerText` and `TrainingText`, which share a private
    base `_ProfileText` carrying `profile_translation_id` and `language`
- Nested values come through `AliasPath`, for example
  `AliasPath("profileTranslation", "languageBranch", "language", "culture")`.
- `SkillRef.keyword_id` is resolved as `Skill.keyword_id` is: top-level `id`
  first, then `keyword.id`. Move that logic out of `Skill`'s validator into a
  module-level helper in `models/skills.py`, which both models' validators
  call. `Skill`'s behaviour does not change, and its existing tests still
  pass. (Calling `Skill`'s private validator directly fails strict pyright.)
- Null lists become `[]`, `is_current: None` becomes `False`, and
  `SkillRef.name: None` becomes `""`. Use one shared `mode="before"` validator
  per model for the list fields, not one per field. Texts are not changed:
  `""` stays `""`.
- `models/__init__` exports every public model above.

Tests:
- [ ] **Review focus 1, 2 and 3:** a synthetic `profile_payload()` maps to the
  expected `model_dump(mode="json")`, checked as one exact dict. The payload
  has:
  - top-level `skills`, `references`, `extSkills` and `commitments` arrays,
    all absent from the dump, while `.raw` still holds `skills`
  - two profile translations (`sv-SE` default, `en-GB`); a presentation with
    both entries, one with `personalDescription: ""`; and one work experience
    with only the `sv-SE` entry
  - that work experience with `endDate: null`, `isCurrent: true` and one
    nested skill (with `changeHistory`, `translations` and
    `keyword.synonyms`), which dumps as `{"keyword_id": ..., "name": ...}`
  - one employer and one training (`trainingType: 1`, `year`, a null
    `expireDate`, `issuer` in its translation entry)
  - `education: null`, which dumps as `[]`
  - `createdWhen` with seven fractional digits
- [ ] Commit: "Add the profile models".

### Task 2: Resume models

**Files:** `src/cinode/models/resumes.py`, `models/__init__.py`,
`tests/support.py` (`resume_summary_payload`, `resume_payload`),
`tests/test_models.py`.

**Consumes:** the patterns from Task 1 (the shared list validator and the
`AliasPath` style).

**Produces:**
- `ResumeSummary`, `Resume(ResumeSummary)` and `ResumeBlock`, as in the
  design's *Resumes* section. `Resume.blocks` comes from
  `AliasPath("resume", "blocks")`, and `ResumeBlock.items` from `data`, as
  `list[dict[str, Any]]`, untouched.
- `models/__init__` exports all three.

Tests:
- [ ] **Review focus 1 and 4:** a synthetic `resume_payload()` maps to the
  expected `model_dump(mode="json")`, checked as one exact dict. The payload
  has:
  - a `resume` with two style keys (for example `pdfMarginTop` and
    `cssVariables`) and a named block copy (`presentation`), all absent from
    the dump
  - three blocks: one with a `data` list of two items (camelCase keys, string
    ids, passed through as they are), one of type 9 with inline `title`,
    `description` and `personalDescription` and no `data` (so `items == []`),
    and one with `data: null` and a `blockType` not seen live (for example
    99)
- [ ] Commit: "Add the resume models".

### Task 3: Profile and resume calls, and their commands

**Files:** `src/cinode/resources/users.py`, `src/cinode/cli/users.py`,
`src/cinode/cli/_output.py`, `src/cinode/cli/schema.py`,
`tests/test_resources.py`, `tests/live/test_acceptance.py`, `README.md`,
`CHANGELOG.md`.

**Consumes:** `Profile`, `ResumeSummary` and `Resume` from Tasks 1 and 2.

**Produces:**
- `UserProfile(Resource)` with `.get(user) -> Profile`, reading
  `users/{u}/profile`, wired in as `Users.profile`.
- `UserResumes(Resource)`, wired in as `Users.resumes`, with:
  - `.list(user) -> list[ResumeSummary]`, reading `users/{u}/resumes`. Its
    docstring says that an empty list can mean no access (see the design's
    note under *Resources*).
  - `.get(user, resume_id) -> Resume`, reading `users/{u}/resumes/{r}`, with
    `resume_id` checked by `require_id(resume_id, "resume_id")`.
- CLI, each command with `--raw` and `--jsonl`:
  - `cinode users profile get <user>`. `profile` has one command, so it gets
    an `@app.callback()`, like `users teams`.
  - `cinode users resumes list <user>`, whose help carries the empty-list
    note.
  - `cinode users resumes get <user> <resume-id>`, where `<resume-id>` is
    `ResumeIdArg`, an `int` argument with `min=1` defined in `cli/_output.py`
    beside `KeywordIdArg`.
- `cinode schema` gains `profile`, `resume` and `resume-summary`.

Tests:
- [ ] **Review focus 5 and 6:** one parametrized resource test, beside
  `test_me_resolves_to_the_token_user`. For the paths:
  - `users.profile.get("me")` requests `/v0.1/companies/99/users/1001/profile`
  - `users.resumes.list("me")` requests `…/users/1001/resumes`
  - `users.resumes.get("me", 7)` requests `…/users/1001/resumes/7`

  For the guard, `resume_id` values `True`, `0` and `"5"` raise `ValueError`,
  and no request is made.
- [ ] Live: `users profile get me`: `.user_id` is the owner, and the output
  validates against `Profile` (as `test_users_skills_list_me` does for
  `Skill`).
- [ ] Live: extend `test_unreadable_user`, or add a case beside it:
  `users profile get <unreadable>` exits 4 or 5 with a `ForbiddenError` or
  `NotFoundError` envelope.
- [ ] Live: `users resumes list me`: every element's `.user_id` is the owner.
  If the list is non-empty, `users resumes get me <first id>` gives that
  `.id` and a non-empty `.blocks`. If it is empty, that half is skipped with
  `pytest.skip` and a message that names no data.
- [ ] README:
  - the library quick start shows `c.users.profile.get("me")` and the resume
    calls
  - the CLI list gains the three commands, with the empty-list note
  - the sentence "Version 0.1 covers …" gains one saying that version 0.2 adds
    profiles and resumes

  CHANGELOG: an entry under *Unreleased*.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m "live
  and not slow"`. Commit in two chunks: "Add users.profile and users.resumes",
  "Add the profile and resume commands".

### Task 4: `ops.team_profiles`

**Files:** `src/cinode/ops/_members.py`, `ops/team_profiles.py`,
`ops/team_skills.py`, `ops/__init__.py`, `src/cinode/cli/teams.py`,
`src/cinode/cli/schema.py`, `tests/test_ops.py`,
`tests/live/test_acceptance.py`, `README.md`, `CHANGELOG.md`.

**Consumes:** `users.profile.get` (Task 3). The loop and `Skipped` move out
of `team_skills.py` in this task; nothing new imports from `team_skills.py`.

**Produces:**
- `ops/_members.py`:
  - `Skipped`, moved from `team_skills.py`, with a docstring that no longer
    names skills. `team_skills.py` and `ops/__init__` re-export it, so
    `from cinode.ops import Skipped` and `from cinode.ops.team_skills import
    Skipped` keep working.
  - `walk_members[E](client: Cinode, team_id: int, entry: Callable[[UserSummary], E], on_progress: Callable[[int, int, E | Skipped], None] | None) -> tuple[Team, list[E], list[Skipped]]`:
    the loop that `team_skills` runs today. It fetches the team, deduplicates
    the members (first-seen order, preferring an entry with the user inline,
    `UserSummary(id=…)` when there is none), calls `entry(user)` per member,
    records a 403 or 404 as `Skipped`, and calls `on_progress`.
  - `team_skills` becomes `walk_members(..., lambda u: MemberSkills(user=u, skills=client.users.skills.list(u.id)), ...)`,
    with its behaviour and public names unchanged. (This signature was
    checked under strict pyright.)
- `team_profiles(client: Cinode, team_id: int, *, on_progress: Callable[[int, int, MemberProfile | Skipped], None] | None = None) -> TeamProfiles`.
- Result models:
  - `MemberProfile(user: UserSummary, profile: Profile)`
  - `TeamProfiles(team: Team, members: list[MemberProfile], skipped: list[Skipped])`,
    with `Skipped` from `_members.py`.
- `ops/__init__` also exports `team_profiles`, `TeamProfiles` and
  `MemberProfile`.
- `cinode teams profiles <team-id>`, with `--jsonl` and no `--raw`, and progress
  on stderr only when it is a TTY, exactly like `teams skills`. It exits 0 even
  when members are skipped. The existing `_progress` in `cli/teams.py` is
  widened to `MemberSkills | MemberProfile | Skipped` and shared by both
  commands.
- `cinode schema` gains `team-profiles`.

Tests:
- [ ] With members 1, 2 and 3, where 2's profile returns 403 and 3's returns
  404: 1 is in `members` with its `Profile`, and `skipped` is
  `[(2, "forbidden"), (3, "not_found")]`. One new test, beside the existing
  `team_skills` test, which stays as it is.
- [ ] **Review focus 7:** the existing `team_skills` tests pass unedited.
- [ ] Live, `@slow`: `teams profiles <team>`. The unique set of member and
  skipped ids equals the unique ids from `teams members list`, and the
  owner's entry in `members` has `.profile.user_id` equal to the owner.
- [ ] README: the quick start and the CLI list gain `team_profiles`.
  CHANGELOG: the *Unreleased* entry covers it.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (the slow tests included, since this is the last task). Commit in two
  chunks: "Share the team member loop between operations", "Add the
  team_profiles operation and command".

---

## Done when

- [ ] `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are
      clean, and the default test run takes under two seconds.
- [ ] `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
      profile.
