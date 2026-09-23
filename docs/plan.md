# cinode-client — plan

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to carry out the tasks in order. Write only the
> tests a task lists; they pin behaviour the design depends on. Do not add
> tests for coverage. Steps use checkboxes for tracking.

**Goal:** v0.1 of a read-only Cinode library and a CLI over it, covering skills.

**Architecture:** a GET-only transport (tokens, rate limits, retries, error
mapping) under namespaced resources that mirror Cinode's URL tree and return
pydantic models. `cinode.ops` holds calls that combine several endpoints. A
typer CLI mirrors the library and writes JSON.

**Tech stack:** Python 3.14, uv, httpx, pydantic v2, typer, pytest, respx, ruff,
pyright.

**Spec:** [`docs/design.md`](design.md). Read it before starting; this plan
does not repeat it.

## Roadmap

| Version | Content |
|---|---|
| **0.1** | This plan: transport, skills, users, teams, keywords, `team_skills`, CLI, live acceptance suite |
| 0.2 | Output for humans (`--table`); user profiles and resumes (`users.profile.get`, `users.resumes.list/get`) |
| 0.3 | More reads as needed: user roles, team managers, keyword lookups |
| — | MCP server, as a **separate project** depending on `cinode-client>=0.1` |
| later | `AsyncCinode`, only if the MCP server needs concurrency |

Each later version gets its own plan, written when it starts.

## Global constraints

- Python `>=3.14`. Runtime dependencies: `httpx>=0.28.1`, `pydantic>=2.13.5`,
  `typer>=0.27.2`. Dev: `pytest>=9.1.1`, `respx>=0.23.1`, `ruff>=0.16.8`,
  `pyright>=1.1.414`.
- Package `cinode-client`, import name `cinode`, `src/` layout, `uv_build`
  backend (`module-name = "cinode"`), console script `cinode = "cinode.cli:main"`.
- **GET only.** No code path issues any other HTTP method.
- No real colleagues' data in the repository. Unit fixtures are synthetic
  (company 99, user 1001, team 500, names like "Ada Example").
- Every commit passes `uv run pytest`, `uv run ruff check`,
  `uv run ruff format --check` and `uv run pyright` (strict, on `src/`).
- Commit messages are plain imperative sentences, with no prefixes and no emoji.
- The default test run (everything except `live`) finishes in **under two
  seconds**. Tests never sleep for real and never touch the network, except
  those marked `live`.
- Few tests: only those listed per task. Parametrize instead of repeating.

## Review focus

Failure modes the spec implies but does not spell out. Each one has a test in
the task named.

1. **No credentials when an agent runs the CLI.** Expect a JSON error on
   stderr, exit 3, no traceback. *(Task 10)*
2. **`CINODE_BASIC` with whitespace inside it.** GNU `base64` wraps output at 76
   characters. Strip all whitespace from the value. *(Task 1)*
3. **Local clock out of step with Cinode's.** Count the token's lifetime from
   when it arrives, on the local clock, so tokens are not refetched on every
   request. *(Task 3)*
4. **Keyword terms with URL-special characters** (`C#`, `CI/CD`, `Språk`,
   spaces). Each term must be sent as one percent-encoded path segment.
   *(Task 8)*
5. **A body that is not JSON** (an HTML page from a proxy, or an empty 200).
   Raise `UnexpectedResponseError`, or `ServerError` for a 5xx, never a raw
   `JSONDecodeError`. The CLI exits 1 with the error envelope. *(Tasks 4, 10)*

## File map

```
pyproject.toml  README.md  CHANGELOG.md  .gitignore
src/cinode/
  __init__.py  _version.py  _config.py  _ratelimit.py  _auth.py  _transport.py
  _client.py  errors.py  py.typed
  models/    __init__.py  _base.py  identity.py  users.py  skills.py  teams.py
  resources/ __init__.py  _base.py  users.py  teams.py  keywords.py
  ops/       __init__.py  team_skills.py
  cli/       __init__.py  _output.py  users.py  teams.py  keywords.py  schema.py
tests/
  support.py            FakeClock, make_jwt, payload factories, constants
  conftest.py           clock, settings, api (respx), transport, client
  test_config.py  test_ratelimit.py  test_auth.py  test_transport.py
  test_models.py  test_resources.py  test_client.py  test_ops.py
  cli/conftest.py  cli/test_cli.py
  live/conftest.py  live/test_acceptance.py  live/test_parity.py
```

---

### Task 1: Scaffold, errors and configuration

**Files:** `pyproject.toml`, `.gitignore`, `README.md` (a stub for now),
`CHANGELOG.md`, `src/cinode/__init__.py`, `src/cinode/_version.py`,
`src/cinode/py.typed`, `.github/workflows/ci.yml`.

- [x] `pyproject.toml` following the global constraints, plus:
  - pytest settings: `testpaths = ["tests"]`, `pythonpath = ["tests"]`,
    markers `live` and `slow`, `addopts = "-m 'not live and not slow'"`,
    strict markers
  - ruff: line length 100; rules `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`;
    `extend-exclude = ["*.md"]`, since ruff also formats Markdown code blocks
  - pyright: `typeCheckingMode = "strict"`, `include = ["src"]`
- [x] `.gitignore`: `.venv/`, the caches, `dist/`, `.env`, and for personnel
  data `data/`, `*.csv`, `*.json`.
- [x] `_version.py` sets `__version__ = importlib.metadata.version("cinode-client")`,
  and `__init__` re-exports it. It lives in its own module so the transport
  can import it without an import cycle.
- [x] `.github/workflows/ci.yml`: on pull requests to `main`, set up uv
  (`astral-sh/setup-uv`), run `uv sync --locked`, then the four checks. No
  secrets, and no live tests.

Also in this task, errors and configuration (`src/cinode/errors.py`,
`src/cinode/_config.py`, `tests/test_config.py`), so the first PR has code
for CI to check.

**Produces:**
- `CinodeError(message, *, status=None, path=None, correlation_id=None)` with
  `.to_dict() -> {"type", "status", "path", "message", "correlation_id"}`.
- Its subclasses:
  - `AuthError`, `ForbiddenError`, `NotFoundError`, `ServerError`,
    `UnexpectedResponseError`
  - `BadRequestError(..., field_errors: dict[str, list[str]])`, which adds
    `field_errors` to `to_dict()`
  - `RateLimitedError(..., retry_after: float | None = None)`, which adds
    `retry_after` to `to_dict()` (added in Task 4)
- `FORBIDDEN_HINT`, a message explaining the owner-context model.
- `Settings(basic, base_url=DEFAULT_BASE_URL, timeout=30.0)`: a frozen
  dataclass, with `basic` hidden from `repr`. Two constructors:
  - `Settings.from_credentials(access_id, access_secret, *, base_url, timeout)`
  - `Settings.from_env(env: Mapping | None = None)`
- `DEFAULT_BASE_URL = "https://api.cinode.com"` (the root, without `/v0.1`).

Tests:
- [x] `from_env`: id and secret win over `CINODE_BASIC`; with neither set,
  `AuthError`.
- [x] **Review focus 2:** `CINODE_BASIC="YWJj\nZGVm \n"` becomes `"YWJjZGVm"`.
- [x] `uv sync`, run the checks, commit in two chunks ("Scaffold the
  cinode-client package", "Add errors and configuration").

### Task 2: Rate limiter

**Files:** `src/cinode/_ratelimit.py`, `tests/support.py` (`FakeClock`),
`tests/test_ratelimit.py`.

**Produces:**
- `RateLimiter(limit: int, window: float, *, clock=time.monotonic, sleep=time.sleep)`
  with `.acquire()`. It is a sliding window over a deque of timestamps. When
  the window is full, it sleeps until the oldest timestamp leaves the window.
- `FakeClock`, used by every later task: callable, returns `t`; its
  `sleep(s)` appends `s` to `sleeps` and advances `t`.

Tests:
- [x] With `(2, 2.0)`: calls at t0 and t0+0.5, then a third call, give
  `sleeps == [1.5]`.
- [x] Commit: "Add a sliding-window rate limiter".

### Task 3: Tokens

**Files:** `src/cinode/_auth.py`, `tests/support.py` (`make_jwt`, constants
`BASE_URL = "https://api.test"`, `USER_ID = 1001`, `COMPANY_ID = 99`),
`tests/conftest.py` (fixtures `clock` and `api`), `tests/test_auth.py`.

**Produces:**
- `Token(value, user_id, company_id, expires_at)`: frozen, with `value`
  hidden from `repr`.
- `decode_token(jwt, *, issued_at) -> Token`.
- `TokenManager(http: httpx.Client, basic: str, limiter: RateLimiter, *, now=time.time)`
  with `.get() -> Token` and `.invalidate()`.

**Decoding:** base64url-decode the JWT payload; the signature is not checked.
`sub` gives the user id and `companySub` the company id. The lifetime is
`exp - iat` when both are present and the difference is finite and positive,
otherwise 120 s, and `expires_at = issued_at + lifetime`. A malformed token
raises `UnexpectedResponseError`.

**Fetching:**
- `GET /token` with `Authorization: Basic …`, after `limiter.acquire()`.
- 400, 401 or 403 → `AuthError`.
- 429 → `RateLimitedError`.
- 5xx → `ServerError`.
- Any other ≥400 → `CinodeError`.
- A body without `access_token` → `UnexpectedResponseError`.
- The manager refetches when less than 30 s of the lifetime remain.

**Test fixtures:**
- `make_jwt(*, iat=0, lifetime=120, sub=USER_ID, company=COMPANY_ID)`.
- `api` is a `respx.mock(base_url=BASE_URL, assert_all_called=False)` router
  with a named `token` route that returns `make_jwt()`.

Tests:
- [x] Two calls to `get()` make one request. Moving the clock to 91 s after
  issue triggers a refetch.
- [x] **Review focus 3:** a token whose `iat` and `exp` are far in the past
  (skewed clocks) is still cached for its full lifetime.
- [x] A 401 from `/token` gives `AuthError`.
- [x] Commit: "Add token exchange and caching".

### Task 4: Transport

**Files:** `src/cinode/_transport.py`, `tests/conftest.py` (fixtures `settings`
and `transport`), `tests/test_transport.py`.

**Consumes:** `Settings`, `RateLimiter`, `TokenManager`, the errors.

**Produces:**
- `Transport(settings, *, clock=time.monotonic, sleep=time.sleep, now=time.time, rng=random.random)`.
- `.get(path: str, *, versioned: bool = True) -> Any`: the path goes under
  `/v0.1/`, or under `/` when `versioned=False`.
- `.tokens: TokenManager`, and `.close()`.
- The class has **no** `post`, `put`, `patch`, `delete` or `request`.
- `API_PREFIX = "/v0.1/"`.

**Behaviour** (see design, *Transport*):
- It owns an `httpx.Client` with the base URL, timeout,
  `Accept: application/json` and `User-Agent: cinode-client/<version>`.
- Two limiters: 40 per 2 s for requests and 2 per 2 s for tokens.
- A 401 invalidates the token and retries once.
- A 429 is retried up to 5 attempts, honouring `Retry-After` in seconds
  (capped at 60).
- 502/503/504 and `httpx.TransportError` are retried up to 3 attempts.
- Backoff is `min(8, 0.5·2^(n-1)) · (0.5 + rng()/2)`.
- Status mapping: 400 → `BadRequestError` with `field_errors` taken from
  `{"errors": {...}}`, 401 → `AuthError`, 403 → `ForbiddenError`
  (`FORBIDDEN_HINT`), 404 → `NotFoundError`, 429 → `RateLimitedError`, 5xx →
  `ServerError`, anything else → `CinodeError`.
- `correlation_id` comes from any response header whose name contains
  "correlation", ignoring case.
- An empty body returns `None`. A body that is not JSON raises
  `UnexpectedResponseError`.

**Fixture:** `transport` uses `clock` for `clock`, `sleep` and `now`, and
`rng=lambda: 1.0`, which makes the backoff deterministic: 0.5, 1, 2, 4.

Tests:
- [x] 401 then 200 succeeds with two token fetches; 401 twice gives `AuthError`.
- [x] 429 with `Retry-After: 3` sleeps `[3.0]`; five 429s give
  `RateLimitedError` after `[0.5, 1, 2, 4]`. Three 503s give `ServerError`.
- [x] One parametrized test of the status mapping: 400 (with `field_errors`),
  403 (with `X-Correlation-Id` and the hint), 404, each raised without retry.
- [x] **Review focus 5:** a 200 with an HTML body gives `UnexpectedResponseError`.
- [x] GET-only: `Transport` has no write-method attributes, and every
  recorded call is a `GET`.
- [x] Commit: "Add the GET-only transport".

### Task 5: Model base, skills and keywords

**Files:** `src/cinode/models/_base.py`, `models/skills.py`,
`models/__init__.py`, `tests/support.py` (`skill_payload`, `keyword_payload`,
shaped like `CompanyUserSkillModel` and `KeywordModel`), `tests/test_models.py`.

**Produces:**
- `CinodeModel`, the base for every model:
  - Config: `frozen=True`, `extra="ignore"`, `validate_by_name=True`,
    `validate_by_alias=True`.
  - `.raw` holds the payload the model was parsed from. It is stored in a
    private attribute set by a `mode="wrap"` model validator whenever the
    input is a dict. `.raw` does not count towards equality: two models are
    equal when their fields are.
  - `.parse(data, *, path=None) -> Self` and `.parse_list(...) -> list[Self]`
    wrap pydantic's `ValidationError` (and a list input that is not a list)
    in `UnexpectedResponseError`. The message gives each error's location
    and message, never the input, and `parse_list` names the failing item's
    index.
- `Keyword` and `Skill`, with fields as in the design tables.
  - Use `AliasPath("keyword", ...)` for the values nested under `keyword`.
  - `keyword_id` is resolved by a `mode="before"` validator: top-level `id`
    first, then `keyword.id`. The spec allows `id` to be null, so
    `AliasChoices` alone would not do.
  - `name` and `Keyword.name`: `None` becomes `""`. `Keyword.synonyms`:
    `None` becomes `[]`.
  - `level`: 0 becomes `None`.
  - `days_experience`: `None` becomes 0.
  - `favourite`: `None` becomes `False`.
  - `is_rated` and `years_experience` (days / 365.25, rounded to 1 decimal)
    are `@computed_field`s.

Tests:
- [x] A real-shaped payload maps to the expected `model_dump(mode="json")`,
  checked as one exact dict. It includes `level: 0` → `None`,
  `is_rated: False`, null `numberOfDaysWorkExperience` → 0, and an extra field
  that is absent from the dump but present in `.raw`.
- [x] Parametrized over the nullable fields: `masterSynonym: null` gives
  `name == ""`, `synonyms: null` gives `[]`, and `id: null` takes
  `keyword.id`.
- [x] Commit: "Add the model base, skills and keywords".

### Task 6: Users, teams and identity models

**Files:** `models/users.py`, `models/teams.py`, `models/identity.py`,
`models/__init__.py`, `tests/support.py` (`user_payload`, `team_payload`,
`member_payload`), `tests/test_models.py`.

**Produces:**
- `UserSummary`: `id` from `AliasChoices("companyUserId", "id")`, first and
  last names, `seo_id`, `user_type`, and a computed `full_name`.
- `User(UserSummary)`: adds `title`, `email`, `location`, `status` and
  `employment_start`.
- `Team`: `id`, `name`, `description`, `parent_team_id`.
- `TeamMember`: `user_id: int`, `team_id`, `user: UserSummary | None` from
  `companyUser`, and `availability_percent`.
  - `user_id` is resolved by a `mode="before"` validator: top-level
    `companyUserId` first, then `companyUser.companyUserId`, then `companyUser.id`. The spec allows
    both to be null, so `AliasChoices` alone would not do.
- `WhoAmI`: `company_id` and `user_id`.
- `models/__init__` exports all of these, plus `CinodeModel`, `Skill` and `Keyword`.

Tests:
- [x] Parametrized over three payloads: the member's user id comes from the
  inline `companyUser`, from a top-level `companyUserId` only (with
  `user=None`), and from the inline one when the top-level one is null.
- [x] Commit: "Add user, team and identity models".

### Task 7: Resources, the client and users

**Files:** `src/cinode/resources/_base.py`, `resources/users.py`,
`resources/__init__.py`, `src/cinode/_client.py`, `src/cinode/__init__.py`,
`src/cinode/_transport.py` (`token()`), `tests/conftest.py` (fixture
`client`), `tests/test_resources.py`,
`tests/test_client.py`.

**Produces:**
- `UserRef: TypeAlias = int | Literal["me"]` (a plain alias, not a `type`
  statement, so `typing.get_args` sees the union).
- `Transport.token() -> Token`: the token, fetched under the same retries,
  error mapping and closed check as `.get()`. Resources read the token only
  through it.
- `require_id(value, name) -> int` in `resources/_base.py`: the one shared id
  guard. It returns `value` if it is a positive `int` that is not a `bool`, and
  raises `ValueError` otherwise.
- `Context(transport)`:
  - `.company_id`, taken from the token.
  - `.user_id(ref) -> int`, where `"me"` gives the token's user id. Anything
    other than exactly `"me"` or a positive non-bool `int` raises `ValueError`
    before any request; digit strings are rejected.
  - `.get(path) -> tuple[Any, str]`, which prefixes `companies/{cid}/` and
    returns the body and the full request path, for errors.
- `Resource(ctx)`, with `._one(Model, path) -> Model` and
  `._list(Model, path) -> list[Model]`, which GET a path below
  `companies/{cid}/` and parse it. Every resource method is one call to them.
- `Users` with `.list()`, `.get(user)`, and `.skills: UserSkills` (`.list(user)`,
  `.get(user, keyword_id)`) and `.teams: UserTeams` (`.list(user)`).
  `keyword_id` is checked with `require_id`.
- `cinode.resources` exports only `UserRef`; `Context`, `Resource` and the
  resource classes are internal.
- `Cinode`:
  - Constructors: `Cinode(access_id, access_secret, *, base_url, timeout)`,
    `Cinode.from_env(env=None)`, and the private
    `Cinode._with_transport(transport)` for tests.
  - Attributes and methods: `.company_id`, `.whoami()` (`_whoami`,
    unversioned), `.users`, `.close()`, and the context-manager methods.
- `cinode/__init__` exports `Cinode`, `UserRef`, the errors and `__version__`.

**Note:** inside a class that defines `list`, annotate return types as
`builtins.list[...]`. Python 3.14 evaluates annotations lazily, and in class
scope `list` would otherwise resolve to the method.

Tests:
- [x] `users.skills.list("me")` requests `/v0.1/companies/99/users/1001/skills`,
  with the company and user ids taken from the token.
- [x] `whoami()` calls `/_whoami`, without the `/v0.1` prefix.
- [x] A first `/token` that returns 503 is retried, and `users.list()` still
  succeeds (added in review).
- [x] A bad user ref (`True`, `0`, `-5`, `"158773"`, `"../../teams"`) raises
  `ValueError` before any request (added in review).
- [x] Commit: "Add the client and the users resources".

### Task 8: Teams and keywords

**Files:** `resources/teams.py`, `resources/keywords.py`, `_client.py`,
`tests/test_resources.py`.

**Produces:**
- `Teams` with `.list()`, `.get(team_id)` and `.members: TeamMembers`
  (`.list(team_id)`).
  - `team_id` is checked with the shared `require_id(team_id, "team_id")` from
    `resources/_base.py`, and every method is one call to `self._one` or
    `self._list`, as in `resources/users.py`.
- `Keywords.search(term)`: raises `ValueError` if the term is not a `str`,
  strips it, raises `ValueError` if it is then empty or made only of dots, and
  encodes it with `quote(term, safe="")`.
- Both are wired in as `Cinode.teams` and `Cinode.keywords`.

Tests:
- [x] **Review focus 4:** parametrized over `C#`, `CI/CD`, `Språk` and
  `machine learning`; each arrives as one segment. Assert on
  `api.calls.last.request.url.raw_path`.
- [x] Rejected terms, parametrized over `""`, `"  "`, `"."`, `".."`, `123`,
  `None` and `b"C#"`: each raises `ValueError` and no request is made.
- [x] Commit: "Add the teams and keywords resources".

### Task 9: `ops.team_skills`

**Files:** `src/cinode/ops/team_skills.py`, `ops/__init__.py`, `tests/test_ops.py`.

**Produces:**
- `team_skills(client: Cinode, team_id: int, *, on_progress: Callable[[int, int, MemberSkills | Skipped], None] | None = None) -> TeamSkills`.
- Result models:
  - `MemberSkills(user: UserSummary, skills: list[Skill])`
  - `Skipped(user: UserSummary, reason: Literal["forbidden", "not_found"])`
  - `TeamSkills(team: Team, members: list[MemberSkills], skipped: list[Skipped])`
- Members are deduplicated by `user_id` in first-seen order, preferring an
  entry that has the user inline. A member with `user=None` becomes
  `UserSummary(id=user_id)`.
- Import `Cinode` only under `TYPE_CHECKING`.

Tests:
- [x] With members 1, 2 and 3, where 2 returns 403 and 3 returns 404: 1 is in
  `members`, and `skipped` is `[(2, "forbidden"), (3, "not_found")]`.
- [x] A persistent 500 on one member raises `ServerError`.
- [x] Commit: "Add the team_skills operation".

### Task 10: CLI core and users

**Files:** `src/cinode/cli/__init__.py`, `cli/_output.py`, `cli/users.py`,
`tests/cli/conftest.py`, `tests/cli/test_cli.py`.

**Produces:**
- `app`, a `typer.Typer` with `no_args_is_help=True`, `add_completion=False`,
  `pretty_exceptions_enable=False` and `rich_markup_mode=None`. Its root group
  class turns any click usage error below it into the error envelope
  (`"type": "UsageError"`, `status`, `path` and `correlation_id` null) on
  stderr, with exit 2. A group given no subcommand still prints its help.
- `main()`, and the `whoami` command.
- `_output`:
  - `run(fetch: Callable[[Cinode], Result], *, raw=False, jsonl=False)`:
    builds `Cinode.from_env()`, and catches only `CinodeError`, writing
    `{"error": e.to_dict()}` to stderr and exiting with `exit_code(e)`
    (Auth 3, Forbidden 4, NotFound 5, RateLimited 6, other 1).
  - `write(result, *, raw, jsonl)` writes `model_dump(mode="json")` or `.raw`.
    `teams skills` (Task 11) offers no `--raw`: `TeamSkills` is built, not parsed.
  - `user_ref(str) -> UserRef` raises `typer.BadParameter` (exit 2) for input
    that is neither numeric nor `me`.
  - Shared `Annotated` types: `RawOption`, `JsonlOption`, `UserArg`.
- `users` commands: `list`, `get`, `skills list`, `skills get`, `teams list`.
- Parse the user argument **before** `run()`, so a usage error does not
  depend on having credentials.
- Sub-apps that have only one command get an `@app.callback()`, so typer
  keeps them as groups.

**Test fixtures:** in `tests/cli/conftest.py`, `cli_api` sets `CINODE_BASIC`
and `CINODE_BASE_URL=https://api.test`, unsets `CINODE_ACCESS_*`, and mocks
`/token`. The mocked token's lifetime is local, so the real clock is fine.
`cli(*args)` wraps `typer.testing.CliRunner().invoke(app, args)`. Assert on
`result.stdout` and `result.stderr` separately.

Tests:
- [x] `users skills list me` writes an array whose element equals the exact
  expected dict. This pins the output contract.
- [x] Parametrized over 403, 404 and 429 (retries used up): exit 4, 5 and 6,
  an empty stdout, and the exact error envelope on stderr.
- [x] **Review focus 1:** with no credentials, exit 3 and a valid JSON
  `AuthError` on stderr.
- [x] `users get Fredrik` gives exit 2, the exact `UsageError` envelope on
  stderr, and makes no request.
- [x] Commit: "Add the CLI with whoami and users commands".

### Task 11: CLI teams, keywords and schema

**Files:** `cli/teams.py`, `cli/keywords.py`, `cli/schema.py`,
`cli/__init__.py`, `tests/cli/test_cli.py`.

**Produces:**
- `teams list [--match TEXT]`, a case-insensitive substring match on the name.
- `teams get`, `teams members list`.
- `teams skills <id>`, which calls `ops.team_skills`. Progress lines go to
  stderr only when `sys.stderr.isatty()`. It exits 0 even when members are
  skipped.
- `keywords search <term>`. An empty term gives `BadParameter`, exit 2. Check
  the term **before** `run()`, in a small helper like `user_ref()`: `run()`
  catches only `CinodeError`, so a `ValueError` raised inside it surfaces as
  a bug (a traceback, exit 1), not as a usage error.
- `schema [model]`. With no argument it writes a sorted JSON array of names;
  with a name it writes `model_json_schema(mode="serialization")`.
  - Names: `skill`, `keyword`, `user`, `user-summary`, `team`, `team-member`,
    `whoami`, `team-skills`.
  - An unknown name gives exit 2 with the valid names in the message.

Tests:
- [x] `teams skills` with one member returning 403 gives exit 0, and the
  `skipped` array holds that member.
- [x] Commit: "Add the teams, keywords and schema commands".

### Task 12: Live acceptance suite

**Files:** `tests/live/conftest.py`, `tests/live/test_acceptance.py`.

**Setup:**
- Each module sets `pytestmark = [pytest.mark.live, skipif(CINODE_LIVE_TESTS != "1")]`.
- The whole suite is skipped when `jq` is not on `PATH`.
- `conftest` provides these session fixtures:
  - `owner`: a dataclass read from the `CINODE_TEST_*` variables, with
    defaults 158773, 9873, 22070, "Python", 2930 and 1.
  - `cinode(*args)`: `subprocess.run` of the installed `cinode` binary
    (`shutil.which`, falling back to the path next to `sys.executable`), with
    captured text output and a 300 s timeout.
  - `jq(expr, document, **argjson) -> bool`: runs `jq -e`.

Tests: the design's acceptance table, one test per row, plus two more:
- [x] `whoami`
- [x] `users get me`
- [x] `users skills list me` (checked with `jq`, then each element passed to
  `Skill.model_validate`)
- [x] `users skills get me <kid>`
- [x] `keywords search <name>`
- [x] `teams members list <team>`
- [x] The unreadable user: exit 4 or 5, and the error `type` in stderr's JSON
  is `ForbiddenError` or `NotFoundError`.
- [x] Added: `--raw` on `skills get` keeps `.keyword.masterSynonym`.
- [x] Added: `teams get <team>`, then `teams list --match <its name>`,
  contains the team.
- [x] `@slow`: `teams skills <team>`. The unique set of member and skipped ids
  equals the unique ids from `teams members list`, and the owner is in
  `members`.
- [x] Run `CINODE_LIVE_TESTS=1 uv run pytest -m "live and not slow"`, then
  `-m live`. Both must pass against the owner's profile.
- [x] Commit: "Add the live acceptance suite".

### Task 13: Parity and documentation

**Files:** `tests/live/test_parity.py`, `README.md`, `CHANGELOG.md`.

**Parity:**
- Marked `live` and `slow`. Skipped unless
  `CINODE_REFERENCE_SCRIPT` (default
  `~/code/sandbox/cinode-helper/fetch-team-skills.py`) exists and
  `CINODE_BASIC` is set.
- Run both tools on the team and compare the two `jq -c` projections:
  - ours: `[.members[] | {user_id: .user.id, skills: ([.skills[] | {keyword_id, level: (.level // 0)}] | sort_by(.keyword_id))}] | sort_by(.user_id)`
  - the script's: `[.[] | {user_id: .id, skills: ([.skills[] | {keyword_id: .id, level}] | sort_by(.keyword_id))}] | sort_by(.user_id)`

**README:** what the project is, and that it is read-only; install
(`uv tool install .`); credentials; library quick start; CLI commands; the
output contract and exit codes; running unit and live tests; the data-handling
rules.

**CHANGELOG:** the 0.1.0 entry.

- [ ] Run `-m live` once more, the parity test included.
- [ ] Commit: "Add the parity check and user documentation".

---

## Done when

- `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are clean,
  and the default test run takes under two seconds.
- `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
  profile, the parity test included.
- `uv tool install .` gives a working `cinode` on `PATH`.
