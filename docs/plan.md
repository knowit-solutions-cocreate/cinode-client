# cinode-client — plan for v0.4

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to carry out the tasks in order. Write only the
> tests a task lists; they pin behaviour the design depends on. Do not add
> tests for coverage. Steps use checkboxes for tracking.

**Goal:** v0.4 lets a human read the CLI's output. `--format table` renders
lists, single objects and `teams skills` as `rich` tables, and `--columns`
picks what they show. Every output choice goes through one option,
`--format json|jsonl|raw|table`, which replaces `--raw` and `--jsonl`.

**Architecture:** CLI only. The library, its models and its JSON output do
not change. `cli/_output.py` gains the `Format` type, the per-command format
options and a `write()` that dispatches on the format. The new module
`cli/_table.py` holds column paths, default columns, `--columns` validation
and rendering. `rich` becomes a declared dependency; it is already installed,
through typer.

**Tech stack:** unchanged, plus `rich` as a direct dependency.

**Spec:** [`docs/design.md`](design.md), in particular *Output contract* and
*Tables* under *CLI*. Read them before starting; this plan does not repeat
them.

## Global constraints

- Everything in v0.3's global constraints still holds: GET only, synthetic
  fixtures (company 99, user 1001), the four checks on every commit, the
  default run under two seconds, only the tests listed, and tests that never
  touch the real home directory.
- **One deliberate break, and nothing else.** `--raw` and `--jsonl` are
  removed, which is recorded under a *Breaking* heading in the CHANGELOG
  (use `--format raw` and `--format jsonl`). Raw output one object per line
  goes with them; `jq -c '.[]'` gives it. Otherwise:
  - The default output of every command is byte for byte what v0.3 wrote.
  - `--format jsonl` and `--format raw` write what `--jsonl` and `--raw`
    wrote.
  - The library's public surface, `cinode schema` and the error envelope do
    not change.
- **Validate before any request.** A refused format, a bad `--columns`, or
  `--columns` without `--format table` exits 2 with the `UsageError`
  envelope, and `respx` sees no request.
- **Tables are loosely pinned.** Their layout is not part of the contract, so
  tests assert labels, cell values, row counts and captions, never box
  characters, padding or widths. Tests that render a table set `COLUMNS=200`
  with `monkeypatch`, so that no cell folds.

## Review focus

Failure modes the design implies but does not spell out. Each one has a test
in the task named.

1. **The default output is unchanged.** An agent calling a command without
   `--format` gets exactly v0.3's bytes. The existing output-shape tests pass
   unedited. *(Task 1)*
2. **The old flags fail loudly.** `--raw` and `--jsonl` are usage errors
   (exit 2) with the JSON envelope, not silently ignored, and not a
   traceback. *(Task 1)*
3. **A format a command does not take is refused, not ignored.** For
   example, `teams skills --format raw` exits 2 before any request, rather
   than writing the built result's `.raw`, which is not JSON. *(Task 1)*
4. **Errors stay JSON on stderr under `--format table`.** A 403 with
   `--format table` writes the usual envelope to stderr and nothing to
   stdout, and exits 4. *(Task 2)*
5. **Column paths come from the models, not from a hand-kept list.** A
   field added to a model later becomes a valid `--columns` path by itself.
   Paths stop at lists (`Resume.blocks`, `Profile.work_experience`), and go
   through nested models, including optional ones (`TeamMember.user`,
   `MemberSkillRow.skill`). *(Task 2)*
6. **A null on the way is an empty cell, not a crash.** A team member whose
   `user` is `None` renders `user.full_name` as an empty cell. *(Task 2)*
7. **`teams skills` loses no member.** A member with no skills still has a
   row, and skipped members are counted in the caption. *(Task 2)*

## File map

```
src/cinode/
  cli/  _output.py  _table.py (new)  __init__.py  users.py  teams.py  keywords.py  config.py
tests/
  cli/test_cli.py  live/test_acceptance.py
pyproject.toml  uv.lock  README.md  CHANGELOG.md
```

---

### Task 1: Replace --raw and --jsonl with --format

**Files:** `src/cinode/cli/_output.py`, `src/cinode/cli/__init__.py`,
`src/cinode/cli/users.py`, `src/cinode/cli/teams.py`,
`src/cinode/cli/keywords.py`, `src/cinode/cli/config.py`,
`tests/cli/test_cli.py`, `tests/live/test_acceptance.py`, `README.md`,
`CHANGELOG.md`.

**Produces:**
- In `cli/_output.py`:
  - `class Format(StrEnum)` with the members `json`, `jsonl`, `raw` and
    `table`. `table` exists from this task on, but no command offers it
    until Task 2.
  - One option alias per format set, each a `typer.Option("--format", ...)`
    whose choices are exactly that set, in the order `json`, `jsonl`, `raw`,
    `table`, so that `--help` lists only what the command takes and anything
    else is a usage error from the parser. The option's parsed value is a
    `Format`, and its default is `Format.json`. How the choices are
    restricted (a `click_type`, or one `StrEnum` per set) is the
    implementer's choice, as long as strict pyright passes and the help text
    lists the choices. The sets in this task, which leave `table` out:
    - `FormatOption`: `json`, `jsonl`, `raw`, for the resource commands and
      `whoami`
    - `TreeFormatOption`: `json`, `jsonl`, `raw`, for `users profile get`
      and `users resumes get`
    - `BuiltFormatOption`: `json`, `jsonl`, for `teams skills` and `teams
      profiles`
    - `ObjectFormatOption`: `json`, for `init` and `config show`
  - `run(fetch, *, format: Format = Format.json)` and
    `write(result, *, format: Format)` replace the `raw` and `jsonl`
    keywords. `write` writes `json`, `jsonl` and `raw` as v0.3 wrote the
    default, `--jsonl` and `--raw`, except that `raw` of a list is always
    one JSON array.
  - `RawOption` and `JsonlOption` are deleted.
- Every command that took `--raw` or `--jsonl` takes `--format` instead,
  with the alias above. `init` and `config show` gain `--format`, and
  `schema` stays without one.
- README: every `--raw` and `--jsonl` becomes `--format raw` or `--format
  jsonl`, and the output section describes `--format` and its values.
  CHANGELOG: an *Unreleased* entry with a *Breaking* line for the removal of
  `--raw` and `--jsonl`, and for raw output one object per line.

Tests:
- [ ] **Review focus 1:** the existing CLI tests pass unedited.
- [ ] One parametrized CLI test of `users skills list me` with two skills:
  - `--format jsonl` writes two lines, each one JSON object
  - `--format raw` writes one JSON array of the two payloads, with their
    camelCase keys
- [ ] **Review focus 2 and 3:** one parametrized CLI test of usage errors,
  each exiting 2 with a `UsageError` envelope on stderr, nothing on stdout,
  and no request:
  - `users skills list me --raw`
  - `users skills list me --jsonl`
  - `teams skills 9873 --format raw`
  - `users profile get me --format table`
- [ ] Live: `test_raw_skill_keeps_the_payload` uses `--format raw`.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (without the slow tests). Commit in two chunks: "Replace --raw and --jsonl
  with --format", "Document --format".

### Task 2: Add table output

**Files:** `src/cinode/cli/_table.py` (new), `src/cinode/cli/_output.py`,
`src/cinode/cli/users.py`, `src/cinode/cli/teams.py`,
`src/cinode/cli/keywords.py`, `src/cinode/cli/config.py`,
`src/cinode/cli/__init__.py`, `tests/cli/test_cli.py`,
`tests/live/test_acceptance.py`, `pyproject.toml`, `uv.lock`, `README.md`,
`CHANGELOG.md`.

**Consumes:** `Format`, the format option aliases, `run` and `write` from
Task 1.

**Produces:**
- `rich` as a runtime dependency, added with `uv add rich`.
- In `cli/_table.py`:
  - `Column`: a frozen dataclass with `path: str` and `label: str`.
  - `column_paths(model: type[CinodeModel]) -> list[str]`: every column path
    of the design's *Column paths* rule, in field order (declared fields,
    then computed ones), found from `model_fields` and
    `model_computed_fields`. It goes into a field whose type, once `None` is
    taken out of an optional, is a `CinodeModel` subclass; it stops at lists
    and dicts, which are not columns; any other type is a scalar column.
  - `DEFAULT_COLUMNS: dict[type[CinodeModel], tuple[Column, ...]]`: the
    design's *Default columns* table.
  - `MemberSkillRow(CinodeModel)`: `user: UserSummary`,
    `skill: Skill | None = None`.
  - `member_skill_rows(result: TeamSkills) -> list[MemberSkillRow]`: one row
    per member and skill, in member order and then Cinode's skill order, and
    one row with `skill=None` for a member with no skills.
  - `parse_columns(value: str | None, model: type[CinodeModel]) -> tuple[Column, ...] | None`:
    `None` when `value` is `None`; otherwise the columns named, labelled as
    the design's *Headers* says. It raises `typer.BadParameter` for an empty
    value, an empty item, or an unknown path, and the message of the last
    lists `column_paths(model)`.
  - `humanise(path: str) -> str`: `"user.full_name"` → `"User full name"`.
  - `render(result: Result, *, columns: tuple[Column, ...] | None, title: str | None = None, caption: str | None = None) -> None`:
    prints a `rich.table.Table` to stdout through a
    `rich.console.Console(highlight=False)`, with every column set to
    `overflow="fold"`. A list uses its element type's defaults unless
    `columns` is given; a single object is a *Field* and *Value* table over
    `column_paths` of its type, or over `columns`. Cells follow the design's
    *Cells* rule.
- In `cli/_output.py`: a `ColumnsOption` alias (`--columns`, `str | None`,
  whose help says that an unknown path lists the valid ones). Each command
  that offers `table` takes it, and calls `parse_columns` with its row model
  before `run()`, so that a bad value exits 2 before any request. `--columns`
  without `--format table` raises `typer.BadParameter`, also before any
  request.
- `write(result, *, format, columns=None, title=None, caption=None)`
  calls `render` for `Format.table`.
- `table` is added to the format sets as the design's table gives them:
  `FormatOption` and `ObjectFormatOption` gain it, and `BuiltFormatOption`
  splits in two, since `teams skills` takes `table` and `teams profiles`
  does not.
- `teams skills` with `--format table` renders `member_skill_rows(result)`
  with the title `result.team.name`, and, when `result.skipped` is not empty,
  the caption "N member(s) skipped: " followed by the counts per reason, in
  the order `forbidden`, `not_found`, leaving out zero counts.
- README: a *Tables* section: `--format table`, `--columns`, an example, and
  that tables are for humans while agents use JSON. The line saying that
  `--table` output is planned goes. CHANGELOG: the
  *Unreleased* entry covers `--format table` and `--columns`.

Tests (with `COLUMNS=200`):
- [ ] One CLI test of `users skills list me --format table` with two skills,
  one of them unrated: stdout holds the six default labels and both skill
  names, the unrated skill's level cell is empty, and stdout is not JSON.
- [ ] **Review focus 5 and 6:** one CLI test of `teams members list 9873
  --format table --columns user_id,user.full_name`, with one member whose
  `companyUser` is null: exit 0, the labels "User id" and "Name", and no
  error.
- [ ] **Review focus 5:** one parametrized test of `column_paths`:
  - `TeamMember` includes `user.full_name` and `user.id`
  - `Resume` includes neither `blocks` nor anything under it
  - `MemberSkillRow` includes `skill.years_experience`
- [ ] One parametrized CLI test of usage errors, each exiting 2 with a
  `UsageError` envelope and no request:
  - `--columns name` without `--format table`: the message names
    `--format table`
  - `--format table --columns bogus`: the message lists `keyword_id`
  - `--format table --columns ""`
  - `--format table --columns name,`
- [ ] One CLI test of `users get me --format table`: stdout holds the
  labels "Field" and "Value", and the rows "Full name" and "Email" with their
  values.
- [ ] **Review focus 7:** one CLI test of `teams skills 9873 --format table`
  with three members: one with two skills, one with none, and one returning
  403. Stdout holds the team's name, both skill names, the second member's
  name, and "1 member skipped: forbidden 1".
- [ ] **Review focus 4:** one CLI test of `users skills list me --format
  table` with a 403: exit 4, the `ForbiddenError` envelope on stderr, and
  stdout empty.
- [ ] Live: `cinode users skills list me --format table` exits 0, and its
  stdout contains the owner's keyword name and does not parse as JSON.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (the slow tests included, since this is the last task). Commit in three
  chunks: "Add rich tables for lists and objects", "Add --columns", "Add a
  table for teams skills".

---

## Done when

- [ ] `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are
      clean, and the default test run takes under two seconds.
- [ ] `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
      profile.
