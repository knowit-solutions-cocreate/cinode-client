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
`cli/_table.py` holds column paths, default columns, rendering and, from
Task 3, `--columns`. `rich` becomes a declared dependency; it is already installed,
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
8. **Cinode's text is data, not markup.** A value holding `[/x]` or
   `:smile:` is printed as it is, and does not crash the renderer or turn
   into an emoji. *(Task 2)*
9. **An empty result still has headers.** An empty list, or a `teams skills`
   whose members were all skipped, renders its row model's headers, which
   is why the row model is passed in rather than read from the first
   element. *(Task 2)*
10. **`--columns` is checked before any request,** in one helper that every
    command calls, not in thirteen copies. *(Task 3)*

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
    `Format`, and its default is `Format.json`. Typer 0.27's vendored click
    has no `Choice`; `click_type=TyperChoice([Format.json, ...])` from
    `typer._types` parses to `Format`, shows `<json|jsonl|raw>` in the help,
    and passes strict pyright (checked while drafting). The sets in this
    task, which leave `table` out:
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
- [x] **Review focus 1:** the existing CLI tests pass unedited.
- [x] One parametrized CLI test of `users skills list me` with two skills:
  - `--format jsonl` writes two lines, each one JSON object
  - `--format raw` writes one JSON array of the two payloads, with their
    camelCase keys
- [x] **Review focus 2 and 3:** one parametrized CLI test of usage errors,
  each exiting 2 with a `UsageError` envelope on stderr, nothing on stdout,
  and no request:
  - `users skills list me --raw`
  - `users skills list me --jsonl`
  - `teams skills 9873 --format raw`
  - `users profile get me --format table`
- [x] Live: `test_raw_skill_keeps_the_payload` uses `--format raw`.
- [x] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
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
  - `humanise(path: str) -> str`: `"user.full_name"` → `"User full name"`.
  - `DEFAULT_COLUMNS: dict[type[CinodeModel], tuple[Column, ...]]`: the
    design's *Default columns* table.
  - `MemberSkillRow(CinodeModel)`: `user: UserSummary`,
    `skill: Skill | None = None`.
  - `member_skill_rows(result: TeamSkills) -> list[MemberSkillRow]`: one row
    per member and skill, in member order and then Cinode's skill order, and
    one row with `skill=None` for a member with no skills.
  - `cells(item: CinodeModel, columns: Sequence[Column]) -> list[str]`: one
    string per column, following the design's *Cells* rule. It is pure, so
    tests assert on cells rather than on rendered box characters.
  - `render(result: Result, *, model: type[CinodeModel], columns: tuple[Column, ...] | None = None, title: str | None = None, caption: str | None = None) -> None`:
    prints a `rich.table.Table` to stdout through
    `rich.console.Console(highlight=False, markup=False, emoji=False)`, with
    every column set to `overflow="fold"`. `model` is the row model, passed
    in by the command, so an empty list still has headers. A list uses
    `DEFAULT_COLUMNS[model]` unless `columns` is given; a single object is a
    *Field* and *Value* table, one row per path of `column_paths(model)` (or
    of `columns`), with the humanised path in *Field*. The title and caption
    are `rich.text.Text(..., no_wrap=True, overflow="ignore")`, so they never
    wrap.
- In `cli/_output.py`: `write(result, *, format, model=None, columns=None, title=None, caption=None)`
  calls `render` for `Format.table`; `run` passes the same keywords through.
  Each command that offers `table` passes its row model.
- `table` is added to the format sets as the design's table gives them:
  `FormatOption` and `ObjectFormatOption` gain it, and `BuiltFormatOption`
  splits in two, since `teams skills` takes `table` and `teams profiles`
  does not.
- `teams skills` with `--format table` renders `member_skill_rows(result)`
  with the model `MemberSkillRow`, the title `result.team.name`, and, when
  `result.skipped` is not empty, the caption "N member(s) skipped: "
  followed by the counts per reason, in the order `forbidden`, `not_found`,
  leaving out zero counts.
- README: a *Tables* section: `--format table`, an example, and that tables
  are for humans while agents use JSON. The line saying that `--table`
  output is planned goes. CHANGELOG: the *Unreleased* entry covers
  `--format table`.

Tests (with `COLUMNS=200`):
- [x] One parametrized CLI test of `users skills list me --format table`:
  - two skills, one of them unrated and one whose name is `[/x] :smile:`:
    exit 0, stdout holds the six default labels and both names exactly as
    given, and is not JSON
  - an empty list: exit 0, and stdout holds the six default labels
- [x] **Review focus 6:** one test of `cells` over `DEFAULT_COLUMNS[Skill]`
  and `DEFAULT_COLUMNS[TeamMember]`: an unrated skill's level cell is `""`,
  `favourite` is `"true"` or `"false"`, and a member whose `user` is `None`
  has `""` for `user.full_name`.
- [x] **Review focus 5:** one parametrized test of `column_paths`:
  - `TeamMember` includes `user.full_name` and `user.id`
  - `Resume` includes neither `blocks` nor anything under it
  - `MemberSkillRow` includes `skill.years_experience`
- [x] One CLI test of `users get me --format table`: stdout holds the
  labels "Field" and "Value", and the rows "Full name" and "Email" with their
  values.
- [x] **Review focus 7 and 9:** one parametrized CLI test of `teams skills
  9873 --format table`:
  - three members, one with two skills, one with none, and one returning
    403: stdout holds the team's name, both skill names, the second member's
    name, and "1 member skipped: forbidden 1"
  - one member, returning 403: exit 0, and stdout holds the default labels
    and "1 member skipped: forbidden 1"
- [x] **Review focus 4:** one CLI test of `users skills list me --format
  table` with a 403: exit 4, the `ForbiddenError` envelope on stderr, and
  stdout empty.
- [x] Live: `cinode users skills list me --format table`, run with
  `COLUMNS=200`, exits 0, and its stdout contains the owner's keyword name
  and does not parse as JSON.
- [x] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (without the slow tests). Commit in two chunks: "Add rich tables for lists
  and objects", "Add a table for teams skills".

### Task 3: Add --columns

**Files:** `src/cinode/cli/_table.py`, `src/cinode/cli/_output.py`,
`src/cinode/cli/users.py`, `src/cinode/cli/teams.py`,
`src/cinode/cli/keywords.py`, `src/cinode/cli/config.py`,
`src/cinode/cli/__init__.py`, `tests/cli/test_cli.py`, `README.md`,
`CHANGELOG.md`.

**Consumes:** `Column`, `column_paths`, `humanise`, `DEFAULT_COLUMNS` and
`render`'s `columns` from Task 2.

**Produces:**
- In `cli/_table.py`: `parse_columns(value: str, model: type[CinodeModel]) -> tuple[Column, ...]`:
  the columns named, in order, each labelled as the design's *Headers* says
  (the label from `DEFAULT_COLUMNS[model]` if the path is there, else
  `humanise(path)`). It raises `typer.BadParameter` for an empty value, an
  empty item, or an unknown path, and the message of the last lists
  `column_paths(model)`.
- In `cli/_output.py`:
  - a `ColumnsOption` alias (`--columns`, `str | None`, whose help says that
    an unknown path lists the valid ones)
  - `table_columns(format: Format, value: str | None, model: type[CinodeModel]) -> tuple[Column, ...] | None`:
    `None` when `value` is `None`; a `typer.BadParameter` naming `--format
    table` when `value` is given with any other format; otherwise
    `parse_columns(value, model)`.
- Every command that offers `table` takes `--columns`, calls `table_columns`
  before `run()`, and passes the result on as `columns`.
- README: the *Tables* section gains `--columns`, with an example, and says
  that a bad path lists the valid ones. CHANGELOG: the *Unreleased* entry
  covers `--columns`.

Tests (with `COLUMNS=200`):
- [ ] One CLI test of `teams members list 9873 --format table --columns
  user_id,user.full_name,team_id`: exit 0, and stdout holds the labels
  "User id", "Name" and "Team id" and not "Availability %".
- [ ] **Review focus 10:** one parametrized CLI test of usage errors on
  `users skills list me`, each exiting 2 with a `UsageError` envelope and
  no request:
  - `--columns name` without `--format table`: the message names
    `--format table`
  - `--format table --columns bogus`: the message lists `keyword_id`
  - `--format table --columns ""`
  - `--format table --columns name,`
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (the slow tests included, since this is the last task). Commit in one
  chunk: "Add --columns".

---

## Done when

- [ ] `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are
      clean, and the default test run takes under two seconds.
- [ ] `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
      profile.
