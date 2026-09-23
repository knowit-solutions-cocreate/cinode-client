# cinode-client — plan

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to carry out the tasks in order. Each task is
> test-first: write the listed tests, see them fail, implement, see them pass,
> run the checks, commit. Steps use checkboxes for tracking.

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
- Tests never sleep for real and never touch the network, except those marked
  `live`.

## Review focus

Failure modes the spec implies but does not spell out. Each one has a test in
the task named.

1. **No credentials when an agent runs the CLI.** Expect a JSON error on
   stderr, exit 3, no traceback. *(Task 11)*
2. **`CINODE_BASIC` with whitespace inside it.** GNU `base64` wraps output at 76
   characters. Strip all whitespace from the value. *(Task 2)*
3. **Local clock out of step with Cinode's.** Count the token's lifetime from
   when it arrives, on the local clock, so tokens are not refetched on every
   request. *(Task 4)*
4. **Keyword terms with URL-special characters** (`C#`, `CI/CD`, `Språk`,
   spaces). Each term must be sent as one percent-encoded path segment.
   *(Task 9)*
5. **A body that is not JSON** (an HTML page from a proxy, or an empty 200).
   Raise `UnexpectedResponseError`, or `ServerError` for a 5xx, never a raw
   `JSONDecodeError`. The CLI exits 1 with the error envelope. *(Tasks 5, 11)*

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

### Task 1: Scaffold

**Files:** `pyproject.toml`, `.gitignore`, `README.md` (a stub for now),
`CHANGELOG.md`, `src/cinode/__init__.py`, `src/cinode/_version.py`,
`src/cinode/py.typed`, `tests/test_package.py`.

- [ ] `pyproject.toml` following the global constraints, plus:
  - pytest settings: `testpaths = ["tests"]`, `pythonpath = ["tests"]`,
    markers `live` and `slow`, `addopts = "-m 'not live and not slow'"`,
    strict markers
  - ruff: line length 100; rules `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`
  - pyright: `typeCheckingMode = "strict"`, `include = ["src"]`
- [ ] `.gitignore`: `.venv/`, the caches, `dist/`, `.env`, and for personnel
  data `data/`, `*.csv`, `*.json`.
- [ ] `_version.py` sets `__version__ = importlib.metadata.version("cinode-client")`,
  and `__init__` re-exports it. It lives in its own module so the transport
  can import it without an import cycle.
- [ ] Test: `cinode.__version__ == "0.1.0"`.
- [ ] `uv sync`, then run the checks and commit: "Scaffold the cinode-client package".

### Task 2: Errors and configuration

**Files:** `src/cinode/errors.py`, `src/cinode/_config.py`, `tests/test_config.py`.

**Produces:**
- `CinodeError(message, *, status=None, path=None, correlation_id=None)` with
  `.to_dict() -> {"type", "status", "path", "message", "correlation_id"}`.
- Its subclasses:
  - `AuthError`, `ForbiddenError`, `NotFoundError`, `RateLimitedError`,
    `ServerError`, `UnexpectedResponseError`
  - `BadRequestError(..., field_errors: dict[str, list[str]])`, which adds
    `field_errors` to `to_dict()`
- `FORBIDDEN_HINT`, a message explaining the owner-context model.
- `Settings(basic, base_url=DEFAULT_BASE_URL, timeout=30.0)`: a frozen
  dataclass, with `basic` hidden from `repr`. Two constructors:
  - `Settings.from_credentials(access_id, access_secret, *, base_url, timeout)`
  - `Settings.from_env(env: Mapping | None = None)`
- `DEFAULT_BASE_URL = "https://api.cinode.com"` (the root, without `/v0.1`).

Tests:
- [ ] `from_credentials` base64-encodes `id:secret`, and either value empty
  gives `AuthError`.
- [ ] `from_env` prefers `CINODE_ACCESS_ID` and `CINODE_ACCESS_SECRET`
  (stripped) and falls back to `CINODE_BASIC`.
- [ ] With neither set, `AuthError`, and the message names both options.
- [ ] **Review focus 2:** `CINODE_BASIC="YWJj\nZGVm \n"` becomes `"YWJjZGVm"`.
- [ ] `CINODE_BASE_URL` overrides the base URL and loses any trailing slash.
- [ ] `CINODE_TIMEOUT` that is not a number or is ≤ 0 gives `CinodeError`.
- [ ] `repr(settings)` does not contain the secret.
- [ ] `BadRequestError.to_dict()` includes `field_errors`.
- [ ] Commit: "Add errors and configuration".

### Task 3: Rate limiter

**Files:** `src/cinode/_ratelimit.py`, `tests/support.py` (`FakeClock`),
`tests/test_ratelimit.py`.

**Produces:**
- `RateLimiter(limit: int, window: float, *, clock=time.monotonic, sleep=time.sleep)`
  with `.acquire()`. It is a sliding window over a deque of timestamps. When
  the window is full, it sleeps until the oldest timestamp leaves the window.
- `FakeClock`, used by every later task: callable, returns `t`; its
  `sleep(s)` appends `s` to `sleeps` and advances `t`.

Tests:
- [ ] `limit` calls in a row do not sleep.
- [ ] With `(2, 2.0)`: calls at t0 and t0+0.5, then a third call, give
  `sleeps == [1.5]`.
- [ ] After the window has passed, calls go through again without sleeping.
- [ ] Commit: "Add a sliding-window rate limiter".

### Task 4: Tokens

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
`exp - iat` when both are present, otherwise 120 s, and
`expires_at = issued_at + lifetime`. A malformed token raises
`UnexpectedResponseError`.

**Fetching:**
- `GET /token` with `Authorization: Basic …`, after `limiter.acquire()`.
- 400, 401 or 403 → `AuthError`.
- 429 → `RateLimitedError`.
- Any other ≥400 → `CinodeError`.
- A body without `access_token` → `UnexpectedResponseError`.
- The manager refetches when less than 30 s of the lifetime remain.

**Test fixtures:**
- `make_jwt(*, iat=0, lifetime=120, sub=USER_ID, company=COMPANY_ID)`.
- `api` is a `respx.mock(base_url=BASE_URL, assert_all_called=False)` router
  with a named `token` route that returns `make_jwt()`.

Tests:
- [ ] `decode_token` reads the user and company ids from string claims.
- [ ] Two calls to `get()` make one request.
- [ ] Advancing the clock to 91 s after issue triggers a refetch.
- [ ] `invalidate()` forces a refetch.
- [ ] The Basic header is sent.
- [ ] A 401 from `/token` gives `AuthError`.
- [ ] A token without `exp` or `iat` gets the 120 s lifetime.
- [ ] Garbage in place of a JWT gives `UnexpectedResponseError`.
- [ ] Three forced refetches in a row sleep on the token limiter (2 per 2 s).
- [ ] **Review focus 3:** a token whose `iat` and `exp` are far in the past
  (skewed clocks) is still cached for its full lifetime.
- [ ] Commit: "Add token exchange and caching".

### Task 5: Transport

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
- [ ] It returns the JSON, sends the Bearer header, and uses the `/v0.1/`
  prefix (none with `versioned=False`).
- [ ] 401 then 200 succeeds, with two token fetches. 401 twice gives `AuthError`.
- [ ] 429 with `Retry-After: 3` sleeps `[3.0]`. Five 429s give
  `RateLimitedError` after sleeping `[0.5, 1, 2, 4]`.
- [ ] 503 then 200 succeeds. Three 503s give `ServerError`.
- [ ] `ConnectError` then 200 succeeds. Repeated `ConnectError` gives `ServerError`.
- [ ] A 403 is not retried and carries the path, `X-Correlation-Id` and the hint.
- [ ] A 404 gives `NotFoundError`. A 400 with an `errors` body gives
  `field_errors`.
- [ ] **Review focus 5:** a 200 with an HTML body gives `UnexpectedResponseError`.
  A 500 with HTML gives `ServerError` with no decoding error. An empty 200
  returns `None`.
- [ ] Advancing the clock by 100 s between calls refreshes the token mid-run.
- [ ] GET-only: every recorded call's method is `GET`, and `Transport` has no
  write-method attributes.
- [ ] Commit: "Add the GET-only transport".

### Task 6: Model base, skills and keywords

**Files:** `src/cinode/models/_base.py`, `models/skills.py`,
`models/__init__.py`, `tests/support.py` (`skill_payload`, `keyword_payload`,
shaped like `CompanyUserSkillModel` and `KeywordModel`), `tests/test_models.py`.

**Produces:**
- `CinodeModel`, the base for every model:
  - Config: `frozen=True`, `extra="ignore"`, `validate_by_name=True`,
    `validate_by_alias=True`.
  - `.raw` holds the payload the model was parsed from. It is stored in a
    private attribute set by a `mode="wrap"` model validator whenever the
    input is a dict.
  - `.parse(data, *, path=None) -> Self` and `.parse_list(...) -> list[Self]`
    wrap pydantic's `ValidationError` (and a list input that is not a list)
    in `UnexpectedResponseError`.
- `Keyword` and `Skill`, with fields as in the design tables.
  - Use `AliasPath("keyword", ...)` for the values nested under `keyword`.
  - `keyword_id` takes `AliasChoices("id", AliasPath("keyword", "id"))`.
  - `level`: 0 becomes `None`.
  - `days_experience`: `None` becomes 0.
  - `favourite`: `None` becomes `False`.
  - `is_rated` and `years_experience` (days / 365.25, rounded to 1 decimal)
    are `@computed_field`s.

Tests:
- [ ] A full payload maps to the expected field values.
- [ ] `level: 0` gives `None` and `is_rated is False`; `level: 3` gives
  `is_rated is True`.
- [ ] Null `levelGoal`, `levelGoalDeadline` and `numberOfDaysWorkExperience`
  are handled. A date-time string parses.
- [ ] `years_experience` for 4242 days is 11.6.
- [ ] An unknown `keyword.type` (for example 999) parses.
- [ ] Extra fields are left out of `model_dump()` but kept in `.raw`.
- [ ] A list of 373 skills parses.
- [ ] `model_dump(mode="json")` has exactly our snake_case keys, the computed
  ones included.
- [ ] Round trip: `Skill.model_validate(skill.model_dump(mode="json")) == skill`.
- [ ] Missing `id` gives `UnexpectedResponseError` with the path.
- [ ] Models are frozen.
- [ ] Commit: "Add the model base, skills and keywords".

### Task 7: Users, teams and identity models

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
    `companyUserId` first, then `companyUser.companyUserId`. The spec allows
    both to be null, so `AliasChoices` alone would not do.
- `WhoAmI`: `company_id` and `user_id`.
- `models/__init__` exports all of these, plus `CinodeModel`, `Skill` and `Keyword`.

Tests:
- [ ] `UserSummary` parses the base payload. `full_name` joins the names and
  skips a missing one.
- [ ] `User` parses the extended fields.
- [ ] A team with `parentTeamId` parses.
- [ ] A member with `companyUser` inline parses.
- [ ] A member with only a top-level `companyUserId` gets `user=None` and the
  right `user_id`.
- [ ] A member with the top-level id null and the inline one set still gets
  the id.
- [ ] `WhoAmI` parses.
- [ ] Commit: "Add user, team and identity models".

### Task 8: Resources, the client and users

**Files:** `src/cinode/resources/_base.py`, `resources/users.py`,
`resources/__init__.py`, `src/cinode/_client.py`, `src/cinode/__init__.py`,
`tests/conftest.py` (fixture `client`), `tests/test_resources.py`,
`tests/test_client.py`.

**Produces:**
- `UserRef = int | Literal["me"]`.
- `Context(transport)`:
  - `.company_id`, taken from the token.
  - `.user_id(ref) -> int`, where `"me"` gives the token's user id.
  - `.get(path)`, which prefixes `companies/{cid}/`.
- `Resource(ctx)`.
- `Users` with `.list()`, `.get(user)`, and `.skills: UserSkills` (`.list(user)`,
  `.get(user, keyword_id)`) and `.teams: UserTeams` (`.list(user)`).
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
- [ ] Each method hits the path in the design's table and returns the right
  model type.
- [ ] `"me"` resolves to `USER_ID` in the path.
- [ ] `company_id` comes from the token without any configuration.
- [ ] `whoami()` calls `/_whoami`, without the `/v0.1` prefix.
- [ ] Building a `Cinode` makes no network call.
- [ ] `with Cinode…` closes the httpx client.
- [ ] A 403 on `users.skills.list(7)` raises `ForbiddenError` with path
  `/v0.1/companies/99/users/7/skills`.
- [ ] Commit: "Add the client and the users resources".

### Task 9: Teams and keywords

**Files:** `resources/teams.py`, `resources/keywords.py`, `_client.py`,
`tests/test_resources.py`.

**Produces:**
- `Teams` with `.list()`, `.get(team_id)` and `.members: TeamMembers`
  (`.list(team_id)`).
- `Keywords.search(term)`: strips the term, raises `ValueError` if it is empty,
  and encodes it with `quote(term, safe="")`.
- Both are wired in as `Cinode.teams` and `Cinode.keywords`.

Tests:
- [ ] The paths and model types are right for all four methods.
- [ ] An empty or whitespace-only term raises `ValueError` without a request.
- [ ] **Review focus 4:** `C#`, `CI/CD`, `Språk` and `machine learning` each
  arrive as one segment. Assert on `api.calls.last.request.url.raw_path`, for
  example `b".../keywords/search/C%23"` and `b".../CI%2FCD"`.
- [ ] Commit: "Add the teams and keywords resources".

### Task 10: `ops.team_skills`

**Files:** `src/cinode/ops/team_skills.py`, `ops/__init__.py`, `tests/test_ops.py`.

**Produces:**
- `team_skills(client: Cinode, team_id: int, *, on_progress: Callable[[int, int, UserSummary], None] | None = None) -> TeamSkills`.
- Result models:
  - `MemberSkills(user: UserSummary, skills: list[Skill])`
  - `Skipped(user: UserSummary, reason: Literal["forbidden", "not_found"])`
  - `TeamSkills(team: Team, members: list[MemberSkills], skipped: list[Skipped])`
- Members are deduplicated by `user_id`, keeping the first. A member with
  `user=None` becomes `UserSummary(id=user_id)`.
- Import `Cinode` only under `TYPE_CHECKING`.

Tests:
- [ ] With members 1, 2 and 3, where 2 returns 403 and 3 returns 404: 1 is in
  `members`, and `skipped` is `[(2, "forbidden"), (3, "not_found")]`.
- [ ] A persistent 500 on one member raises `ServerError`, ending the run.
- [ ] `on_progress` is called with `(1, 3, …)`, `(2, 3, …)` and `(3, 3, …)`.
- [ ] A duplicate member's skills are fetched once.
- [ ] A member without an inline user is still fetched.
- [ ] An empty team gives empty lists.
- [ ] Commit: "Add the team_skills operation".

### Task 11: CLI core and users

**Files:** `src/cinode/cli/__init__.py`, `cli/_output.py`, `cli/users.py`,
`tests/cli/conftest.py`, `tests/cli/test_cli.py`.

**Produces:**
- `app`, a `typer.Typer` with `no_args_is_help=True`, `add_completion=False`
  and `pretty_exceptions_enable=False`.
- `main()`, and the `whoami` command.
- `_output`:
  - `run(fetch: Callable[[Cinode], Result], *, raw=False, jsonl=False)`:
    builds `Cinode.from_env()`, and catches `CinodeError`, writing
    `{"error": e.to_dict()}` to stderr and exiting with `exit_code(e)`
    (Auth 3, Forbidden 4, NotFound 5, RateLimited 6, other 1).
  - `write(result, *, raw, jsonl)` writes `model_dump(mode="json")` or `.raw`.
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
- [ ] `users skills list me` writes an array whose element equals the exact
  expected dict (all snake_case keys, the computed ones included). This pins
  the output contract.
- [ ] `--jsonl` writes one object per line.
- [ ] `--raw` writes Cinode's camelCase payload.
- [ ] `whoami` writes `{"company_id": 99, "user_id": 1001}`.
- [ ] A 403 gives exit 4, an empty stdout and the exact error envelope on
  stderr. A 404 gives exit 5 and a 429 (retries used up) gives exit 6.
- [ ] **Review focus 1:** with no credentials, exit 3, and stderr holds valid
  JSON with type `AuthError` and no traceback.
- [ ] `users get Fredrik` gives exit 2 and makes no request.
- [ ] **Review focus 5:** a 200 with an HTML body gives exit 1 and the error
  envelope.
- [ ] Commit: "Add the CLI with whoami and users commands".

### Task 12: CLI teams, keywords and schema

**Files:** `cli/teams.py`, `cli/keywords.py`, `cli/schema.py`,
`cli/__init__.py`, `tests/cli/test_cli.py`.

**Produces:**
- `teams list [--match TEXT]`, a case-insensitive substring match on the name.
- `teams get`, `teams members list`.
- `teams skills <id>`, which calls `ops.team_skills`. Progress lines go to
  stderr only when `sys.stderr.isatty()`. It exits 0 even when members are
  skipped.
- `keywords search <term>`. An empty term gives `BadParameter`, exit 2.
- `schema [model]`. With no argument it writes a sorted JSON array of names;
  with a name it writes `model_json_schema(mode="serialization")`.
  - Names: `skill`, `keyword`, `user`, `user-summary`, `team`, `team-member`,
    `whoami`, `team-skills`.
  - An unknown name gives exit 2 with the valid names in the message.

Tests:
- [ ] `--match cocreate` keeps only the matching teams, ignoring case.
- [ ] `teams skills` with one member returning 403 gives exit 0, and the
  `skipped` array holds that member.
- [ ] Under CliRunner (not a TTY), stderr is empty.
- [ ] `keywords search "C#"` hits the encoded path.
- [ ] `schema` lists the names. `schema skill` has the properties
  `is_rated` and `years_experience`. `schema nope` gives exit 2.
- [ ] Commit: "Add the teams, keywords and schema commands".

### Task 13: Live acceptance suite

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
- [ ] `whoami`
- [ ] `users get me`
- [ ] `users skills list me` (checked with `jq`, then each element passed to
  `Skill.model_validate`)
- [ ] `users skills get me <kid>`
- [ ] `keywords search <name>`
- [ ] `teams members list <team>`
- [ ] The unreadable user: exit 4 or 5, and the error `type` in stderr's JSON
  is `ForbiddenError` or `NotFoundError`.
- [ ] Added: `--raw` on `skills get` keeps `.keyword.masterSynonym`.
- [ ] Added: `teams get <team>`, then `teams list --match <its name>`,
  contains the team.
- [ ] `@slow`: `teams skills <team>`. The unique set of member and skipped ids
  equals the unique ids from `teams members list`, and the owner is in
  `members`.
- [ ] Run `CINODE_LIVE_TESTS=1 uv run pytest -m "live and not slow"`, then
  `-m live`. Both must pass against the owner's profile.
- [ ] Commit: "Add the live acceptance suite".

### Task 14: Parity and documentation

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

- `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are clean.
- `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
  profile, the parity test included.
- `uv tool install .` gives a working `cinode` on `PATH`.
