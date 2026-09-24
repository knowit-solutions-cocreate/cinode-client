# cinode-client — plan for v0.2

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to carry out the tasks in order. Write only the
> tests a task lists; they pin behaviour the design depends on. Do not add
> tests for coverage. Steps use checkboxes for tracking.

**Goal:** v0.2 adds user profiles and resumes to the library and the CLI, as
lean, typed projections of Cinode's very large payloads.

**Architecture:** no new layers. Two sub-resources join `Users`
(`UserProfile`, `UserResumes`), two model modules join `cinode.models`
(`profiles.py`, `resumes.py`), and the CLI's `users` group gains `profile` and
`resumes`. Everything follows the v0.1 patterns: `Resource._one` and `._list`,
`require_id`, `CinodeModel` with `.raw`, `run()` in the CLI.

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
  `cinode.models`, commands to `cinode users`, and names to `cinode schema`.
- **Fixtures are small.** A synthetic profile or resume payload has one or two
  elements per section and a few of the keys v0.2 leaves out, enough to show
  that they are dropped. Never copy a live payload, even anonymised.
- **Live tests never show live text.** Profiles and resumes are free text about
  a person. Follow the pattern in `tests/live/test_acceptance.py`: bind each
  check to a name before asserting, and never put output in a message.

## Review focus

Failure modes the design implies but does not spell out. Each one has a test
in the task named.

1. **The lean projection stays lean.** A dumped `Profile` has no `skills` key,
   and a work experience's skills dump as `{keyword_id, name}` only. A dumped
   `Resume` has no template settings and no named block copies. Otherwise an
   agent gets hundreds of kilobytes it did not ask for. *(Tasks 1, 2)*
2. **Seven fractional digits, no timezone.** `"2026-01-02T03:04:05.1234567"`
   parses to a naive `datetime` with microseconds `123456`, not an
   `UnexpectedResponseError`. *(Task 1)*
3. **The spec is wrong about resume content.** `resumes.get` reads
   `resumes/{id}` and takes the blocks from `resume.blocks`. It never calls
   `resumes/{id}/dynamic`, which returns 404. *(Task 2)*
4. **Open shapes in resume blocks.** A string `blockId`, an unknown
   `blockType`, a block with inline texts and no `data`, and a `data: null`
   all parse. *(Task 2)*
5. **A bad resume id is refused before any request.** `True`, `0` and `"5"`
   raise `ValueError`, as for every other id. *(Task 2)*

## File map

```
src/cinode/
  models/     profiles.py (new)  resumes.py (new)  __init__.py
  resources/  users.py
  cli/        users.py  schema.py
tests/
  support.py            profile_payload, resume_summary_payload, resume_payload
  test_models.py  test_resources.py
  live/test_acceptance.py
README.md  CHANGELOG.md
```

---

### Task 1: Profiles

**Files:** `src/cinode/models/profiles.py`, `models/__init__.py`,
`src/cinode/resources/users.py`, `src/cinode/cli/users.py`,
`src/cinode/cli/schema.py`, `tests/support.py` (`profile_payload`),
`tests/test_models.py`, `tests/test_resources.py`,
`tests/live/test_acceptance.py`, `README.md`, `CHANGELOG.md`.

**Produces:**
- In `models/profiles.py`, the models of the design's *Profile* section:
  - `Profile`, `Presentation`, `WorkExperience`, `Education`,
    `ProfileLanguage` and `SkillRef`
  - the text entries `PresentationText`, `WorkExperienceText` and
    `EducationText`, which share a private base `_ProfileText` carrying
    `profile_translation_id` and `language`
- Nested values come through `AliasPath`, for example
  `AliasPath("profileTranslation", "languageBranch", "language", "culture")`.
- `SkillRef.keyword_id` is resolved as `Skill.keyword_id` is: top-level `id`
  first, then `keyword.id`. Reuse the validator's logic rather than copying it,
  if that can be done without changing `Skill`.
- Null lists become `[]`, `is_current: None` becomes `False`, and
  `SkillRef.name: None` becomes `""`. Use one shared `mode="before"` validator
  per model for the list fields, not one per field.
- `models/__init__` exports `Profile`, `Presentation`, `PresentationText`,
  `WorkExperience`, `WorkExperienceText`, `Education`, `EducationText`,
  `ProfileLanguage` and `SkillRef`.
- `UserProfile(Resource)` with `.get(user) -> Profile`, which reads
  `users/{u}/profile`, wired in as `Users.profile`.
- The CLI command `cinode users profile get <user>`, with `--raw` and
  `--jsonl`. `profile` has one command, so it gets an `@app.callback()`, like
  `users teams`.
- `cinode schema` gains `profile`.

Tests:
- [ ] **Review focus 1 and 2:** a synthetic `profile_payload()` maps to the
  expected `model_dump(mode="json")`, checked as one exact dict. The payload
  has:
  - a top-level `skills` array, and `employers`, `training`, which are absent
    from the dump
  - one work experience with `endDate: null`, `isCurrent: true`, one
    translation and one nested skill (with `changeHistory`, `translations` and
    `keyword.synonyms`), which dumps as `{"keyword_id": ..., "name": ...}`
  - `education: null`, which dumps as `[]`
  - `createdWhen` with seven fractional digits
  - `.raw` still holding `skills`.
- [ ] Extend `test_me_resolves_to_the_token_user`, or add one parametrized
  case beside it: `users.profile.get("me")` requests
  `/v0.1/companies/99/users/1001/profile`.
- [ ] Live: `users profile get me`: `.user_id` is the owner, and the output
  validates against `Profile` (as `test_users_skills_list_me` does for
  `Skill`).
- [ ] Live: extend `test_unreadable_user`, or add a case beside it:
  `users profile get <unreadable>` exits 4 or 5 with a `ForbiddenError` or
  `NotFoundError` envelope.
- [ ] README: the library quick start shows `c.users.profile.get("me")`; the
  CLI list gains the command; "Version 0.1 covers …" becomes a sentence that
  covers profiles and resumes. CHANGELOG: an entry under *Unreleased*.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m "live and
  not slow"`. Commit in two chunks: "Add the profile models", "Add
  users.profile.get and its command".

### Task 2: Resumes

**Files:** `src/cinode/models/resumes.py`, `models/__init__.py`,
`src/cinode/resources/users.py`, `src/cinode/cli/users.py`,
`src/cinode/cli/schema.py`, `tests/support.py` (`resume_summary_payload`,
`resume_payload`), `tests/test_models.py`, `tests/test_resources.py`,
`tests/live/test_acceptance.py`, `README.md`, `CHANGELOG.md`.

**Consumes:** the patterns from Task 1 (the shared list validator, the
`AliasPath` style, the CLI callback for a one-command group).

**Produces:**
- `ResumeSummary`, `Resume(ResumeSummary)` and `ResumeBlock`, as in the
  design's *Resumes* section. `Resume.blocks` comes from
  `AliasPath("resume", "blocks")`, and `ResumeBlock.items` from `data`, as
  `list[dict[str, Any]]`, untouched.
- `models/__init__` exports all three.
- `UserResumes(Resource)` with:
  - `.list(user) -> list[ResumeSummary]`, reading `users/{u}/resumes`. Its
    docstring says that an empty list can mean no access (see the design's
    note under *Resources*).
  - `.get(user, resume_id) -> Resume`, reading `users/{u}/resumes/{r}`, with
    `resume_id` checked by `require_id(resume_id, "resume_id")`.
  - Wired in as `Users.resumes`.
- CLI:
  - `cinode users resumes list <user>`, whose help carries the same note.
  - `cinode users resumes get <user> <resume-id>`, where `<resume-id>` is an
    `int` argument with `min=1`, like `KeywordIdArg`.
  - Both take `--raw` and `--jsonl`.
- `cinode schema` gains `resume` and `resume-summary`.

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
- [ ] **Review focus 3 and 5:** one parametrized resource test. For the paths,
  `users.resumes.list("me")` requests `…/users/1001/resumes`, and
  `users.resumes.get("me", 7)` requests `…/users/1001/resumes/7`. For the
  guard, `resume_id` values `True`, `0` and `"5"` raise `ValueError`, and no
  request is made.
- [ ] Live: `users resumes list me`: every element's `.user_id` is the owner.
  If the list is non-empty, `users resumes get me <first id>` gives that
  `.id` and a non-empty `.blocks`. If it is empty, that half is skipped with
  `pytest.skip` and a message that names no data.
- [ ] README: the quick start and the CLI list gain the resume calls, with the
  empty-list note. CHANGELOG: the entry under *Unreleased* covers resumes.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (the slow test included, since this is the last task). Commit in two chunks:
  "Add the resume models", "Add users.resumes and its commands".

---

## Done when

- [ ] `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are
      clean, and the default test run takes under two seconds.
- [ ] `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
      profile.
- [ ] `cinode users profile get me | wc -c` is a small fraction of the same
      command with `--raw`.
