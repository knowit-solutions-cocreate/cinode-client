# cinode-client — design

A read-only Python library for the Cinode API, and a CLI over it. Agents are the
first audience: the library is meant to be wrapped by an MCP server (a separate,
later project), and the CLI is meant to be driven by chat agents. Humans come
second.

Version 1 covers skills, plus the users, teams and keywords needed to reach them.
The structure is built so the rest of the API can be added without breaking what
is already there.

## Goals

- **Read-only, by construction.** The transport can only issue GET. No write
  path exists to be enabled by mistake, so the tool can be given to a colleague
  or an agent without risk.
- **Grows without breaking.** Adding a new area of the API means adding modules;
  existing names, signatures and output shapes do not change.
- **Agent-shaped.** Every library call has flat, typed arguments and returns a
  pydantic model. That maps one-to-one onto an MCP tool with a JSON Schema. The
  CLI emits stable JSON with documented exit codes.
- **Correct under the API's real constraints.** The short token lifetime, the
  per-second rate limits and 403s that depend on whose data is asked for are all
  handled inside the library, not left to callers.

## Non-goals

- **Writes.** No PUT, POST, PATCH or DELETE, not behind a flag and not in a
  subclass. A future profile editor is a separate project.
- **The MCP server.** It will be a separate project that depends on this
  library. This design makes that wrapper thin; it does not build it.
- **Skill sets.** `GET companies/{cid}/skill-sets` returns 403 for a non-admin
  owner and there is no per-set read. It cannot work from an ordinary account.
- **Async.** A sync client covers the CLI and a first MCP server. An async
  transport can be added later behind the same resource classes (see
  *Extending*).
- **Caching or local storage.** Callers persist what they want.
- **Committed personnel data.** See *Data handling*.

## The API, as verified

Verified against the live API and the spec on 2026-09-22/23. Background:
`~/notes/cinode-api.md`.

**Base URL:** `https://api.cinode.com/v0.1/`. Two routes sit outside it:
`https://api.cinode.com/token` and `https://api.cinode.com/_whoami`.

**Auth.** An API account has an AccessId and an AccessSecret.
`GET /token` with `Authorization: Basic base64(id:secret)` returns
`{"access_token": <JWT>, "refresh_token": ...}`. The JWT carries `sub` (the
owner's companyUserId), `companySub` (the company id) and `exp`.
**Tokens live 120 seconds.** Because the exchange is itself a GET, the whole
client, auth included, is GET-only.

**Owner context.** Every request runs as the user who owns the API account. The
client can reach exactly what that user can reach, so a 403 is a normal outcome
that depends on the data: 6 of 56 members of one team return 403 on their skills.

**Rate limits** (from Cinode's README, not measured):

| | per day | per 2 s |
|---|---|---|
| normal endpoints | 10,000 | 40 |
| `/token` | 10,000 | **2**, per AccessId |

Fetching a token per request trips the token limit at once, so caching the
token is required for correctness, not just speed.

**No pagination on GET.** Collections come back whole: 478 teams, 141 skills,
all members.

**The spec** (`https://api.cinode.com/swagger/v0.1/swagger.json`, OpenAPI 3.0.4,
public) is a reference, not an input to a build step. It is unreliable:

- Only 64 of 421 schemas declare `required`.
- 304 properties hide their enum values in prose descriptions.
- `OPTIONS` on a path returns an `allow` header with the real methods, which is
  more trustworthy than the spec.

## Architecture

```
CLI (typer)        cinode users skills list me
   │
Library API        Cinode ── .users ── .skills / .teams
   │                      ── .teams ── .members
   │                      ── .keywords
   │               cinode.ops.team_skills(...)
   │
Resources          one class per URL segment; builds paths, parses models
   │
Transport          GET only · token manager · rate limiters · retries · errors
   │
httpx.Client
```

Each layer depends only on the layer below it. Nothing imports the CLI.

### Package layout

```
src/cinode/
  __init__.py          public API: Cinode, models, errors, __version__
  _client.py           Cinode: construction, identity, resource wiring
  _config.py           credentials and settings from args or environment
  _transport.py        Transport: get(), retries, error mapping
  _auth.py             TokenManager: exchange, JWT claims, expiry
  _ratelimit.py        sliding-window limiter with an injectable clock, and Retry-After parsing
  errors.py            exception hierarchy
  models/
    _base.py           CinodeModel base config
    identity.py        WhoAmI
    users.py           UserSummary, User
    skills.py          Skill, Keyword
    teams.py           Team, TeamMember
  resources/
    _base.py           Resource base, UserRef resolution, id checks
    users.py           Users, UserSkills, UserTeams
    teams.py           Teams, TeamMembers
    keywords.py        Keywords
  ops/
    team_skills.py     team_skills(), TeamSkills
  cli/
    __init__.py        typer app, entry point
    _output.py         JSON/JSONL emitting, error envelope, exit codes
    users.py  teams.py  keywords.py  schema.py
```

Modules whose names start with an underscore are private. The public surface is
what `cinode/__init__.py`, `cinode.models`, `cinode.errors` and `cinode.ops`
export.

## Library API

```python
from cinode import Cinode

c = Cinode.from_env()
c = Cinode(access_id="...", access_secret="...")

c.company_id                              # from the JWT
c.whoami()                                # -> WhoAmI

c.users.list()                            # -> list[UserSummary]
c.users.get(user)                         # -> User
c.users.skills.list(user)                 # -> list[Skill]
c.users.skills.get(user, keyword_id)      # -> Skill
c.users.teams.list(user)                  # -> list[Team]

c.teams.list()                            # -> list[Team]
c.teams.get(team_id)                      # -> Team
c.teams.members.list(team_id)             # -> list[TeamMember]

c.keywords.search(term)                   # -> list[Keyword]

from cinode.ops import team_skills
team_skills(c, team_id)                   # -> TeamSkills
```

Wherever a user is expected, the argument is a `UserRef = int | Literal["me"]`,
and `"me"` resolves to the token's `sub`. `UserRef` is a plain `TypeAlias`, so
`typing.get_args(UserRef)` gives `(int, Literal["me"])`.

Ids are checked before any request, because callers such as an MCP server pass
values an agent supplied, and type hints do nothing at run time. A user ref must
be exactly `"me"` or a positive `int` that is not a `bool`; digit strings such
as `"158773"` are rejected, and the CLI converts its arguments before calling.
Every other id (`keyword_id`, `team_id`) must be a positive `int` that is not a
`bool`. A keyword search term must be a `str`; it is stripped, and a term that
is then empty or made only of dots (`.`, `..`) is rejected, since httpx would
collapse it as a dot segment and reach a different endpoint. Anything else
raises `ValueError`.

`Cinode` is a context manager and owns its `httpx.Client`:
`with Cinode.from_env() as c: ...`.

### Resources

The resources mirror the URL tree. A `Resource` holds the transport and the
company id and builds paths below `companies/{cid}/`. It reads the company id
and `"me"` from the token through the transport, so even the first token fetch
is retried and mapped like any other request. A sub-resource is an
attribute of its parent (`Users.skills` is a `UserSkills`), and it takes the
parent's id as its first argument. The client stays stateless, and every
method is a complete, self-describing call.

Method names are fixed across resources: `list` returns a collection, `get`
returns one item, and `search` runs a term query. New resources follow the same
convention.

| Method | Path (under `v0.1/companies/{cid}/`) | Cinode schema |
|---|---|---|
| `users.list()` | `users` | `CompanyUserExtendedModel[]` |
| `users.get(u)` | `users/{id}` | `CompanyUserModel` |
| `users.skills.list(u)` | `users/{u}/skills` | `CompanyUserSkillModel[]` |
| `users.skills.get(u, k)` | `users/{u}/skills/{k}` | `CompanyUserSkillModel` |
| `users.teams.list(u)` | `users/{u}/teams` | `TeamBaseModel[]` |
| `teams.list()` | `teams` | `TeamModel[]` |
| `teams.get(t)` | `teams/{id}` | `TeamModel` |
| `teams.members.list(t)` | `teams/{t}/members` | `TeamMemberModel[]` |
| `keywords.search(q)` | `keywords/search/{term}` | `KeywordModel[]` |
| `whoami()` | `/_whoami` (outside `v0.1`) | `WhoAmIResponseModel` |

### Operations

`cinode.ops` holds functions that combine several calls. They are kept apart
from resources so that resources stay one-to-one with endpoints.

```python
result = team_skills(c, 9873, on_progress=None)
result.team        # Team
result.members     # list[MemberSkills(user: UserSummary, skills: list[Skill])]
result.skipped     # list[Skipped(user: UserSummary, reason: "forbidden" | "not_found")]
```

A 403 or 404 on one member is recorded in `skipped` and never ends the run.
Other errors do end it. `on_progress(done, total, user)` is an optional
callback; the library does no printing of its own.

## Models

Pydantic v2 models with a shared base:

```python
class CinodeModel(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="ignore", validate_by_name=True, validate_by_alias=True
    )
```

- **Our field names, not Cinode's.** Models are snake_case and use domain names
  (`Skill`, not `CompanyUserSkillModel`). Cinode's camelCase is mapped with
  `validation_alias`, including `AliasPath` for nested values. Output always
  uses our names.
- **Only IDs are required.** Because the spec's `required` means nothing, every
  field other than an entity's id is optional with a default.
- **Raw payload kept.** Every model keeps the dict it was parsed from as a
  private attribute, exposed as `.raw`. Callers and the CLI (`--raw`) can reach
  fields the models don't cover without the models' output shape filling up
  with camelCase leftovers. `.raw` does not count towards equality: two models
  with the same fields are equal.
- **Enums are open.** Values found only in prose (`companyUserType`,
  `keyword.type`) are `int` fields, not closed enums, so a new value from Cinode
  does not break parsing.

### Skill

| Field | Source | Notes |
|---|---|---|
| `keyword_id: int` | `id`, else `keyword.id` | the id that item routes use |
| `name: str` | `keyword.masterSynonym` | null → `""` |
| `synonym_id: int \| None` | `keyword.masterSynonymId` | |
| `keyword_type: int \| None` | `keyword.type` | |
| `level: int \| None` | `level` | **0 → `None`**: unrated, not beginner |
| `level_goal: int \| None` | `levelGoal` | |
| `level_goal_deadline: datetime \| None` | `levelGoalDeadline` | |
| `days_experience: int` | `numberOfDaysWorkExperience` | null → 0 |
| `years_experience: float` | computed | `days / 365.25`, 1 decimal |
| `favourite: bool` | `favourite` | |
| `user_id: int` | `companyUserId` | |

Treating an unrated 0 as a real level would quietly skew every average, so the
model does not pass it through. `is_rated` is a computed boolean.

### The others

- `Keyword`: `id`, `name` (`masterSynonym`), `synonym_id`, `type`,
  `synonyms: list[str]`, `verified`.
- `UserSummary`: `id` (`companyUserId`, else `id`), `first_name`, `last_name`,
  `full_name` (computed), `seo_id`, `user_type` (`companyUserType`).
- `User(UserSummary)`: adds `title`, `email` (`companyUserEmail`), `location`
  (`locationName`), `status`, `employment_start` (`employmentStartDate`). More
  fields can be added without breaking anything.
- `Team`: `id`, `name`, `description`, `parent_team_id`.
- `TeamMember`: `user_id` (`companyUserId`, else `companyUser`'s id), `team_id`,
  `user: UserSummary | None` (from `companyUser`), `availability_percent`.
- `WhoAmI`: `company_id`, `user_id`.

## Transport

`Transport.get(path, *, versioned=True) -> Any` and `Transport.token()` are the
only ways to reach the network, and both issue only GET. Paths go under
`/v0.1/`, or under `/` with `versioned=False` (for `/_whoami`). There is no
`post`, `put` or `request`. The CLI and resources go through them, and a test
asserts that `httpx` never sees any method other than GET.

**Tokens.** `TokenManager` exchanges credentials, decodes the JWT payload
(base64 only; the signature is not verified, since the claims are used only for
routing and expiry) and caches the token. The token's lifetime (`exp - iat`) is
counted from the moment it arrives, using the local clock, so a local clock that
is out of step with Cinode's does no harm. It refreshes when less than 30 s of
that lifetime remain, and refreshes once on a 401 before retrying the request. A
second 401 raises `AuthError`.

**Rate limits.** Two sliding-window limiters: `/token` at 2 per 2 s and normal
endpoints at 40 per 2 s. When a window is full, the caller blocks until a slot
opens. The clock and sleep function are injected, so tests run instantly. The
limiters count only within one process; several processes sharing an AccessId
(for example an MCP server and a CLI) are not coordinated, and the 429 retry
covers that case.

**Retries.** Every call is a GET, so every retry is safe.

| Condition | Action |
|---|---|
| 429 | back off (honour `Retry-After`, else exponential with jitter), up to 5 attempts |
| 502, 503, 504, connect/read error | back off, up to 3 attempts |
| 401 | refresh token, retry once |
| other 4xx | raise immediately |

The token fetch is part of each attempt, so a network error, 429 or
502/503/504 from `/token` is retried the same way, `Retry-After` included. An
error from the token fetch has `path` `/token`. A network error that outlasts
its retries raises a plain `CinodeError`.

**Timeouts.** 30 s by default, configurable.

### Errors

```
CinodeError                     status, path, correlation_id, message
├── AuthError                   401 after refresh, or bad credentials at /token
├── ForbiddenError              403 — message explains the owner-context model
├── NotFoundError               404
├── RateLimitedError            429 after retries are used up; .retry_after
├── BadRequestError             400 — .field_errors from {"errors": {...}}
├── ServerError                 5xx after retries
└── UnexpectedResponseError     body failed to parse into the model
```

`correlation_id` is taken from Cinode's response header when present, so a
failure can be reported to Cinode support.

## Configuration

| Setting | Argument | Environment |
|---|---|---|
| credentials | `access_id`, `access_secret` | `CINODE_ACCESS_ID` + `CINODE_ACCESS_SECRET`, or `CINODE_BASIC` |
| base URL | `base_url` | `CINODE_BASE_URL` (tests only) |
| timeout | `timeout` | `CINODE_TIMEOUT` |

The company id and user id are never configured; they come from the token.
Secrets are never logged and never shown in `repr`.

## CLI

Built with typer. Its commands mirror the library, so anyone who knows one
knows the other.

```
cinode whoami
cinode users list
cinode users get <user>
cinode users skills list <user>
cinode users skills get <user> <keyword-id>
cinode users teams list <user>
cinode teams list [--match TEXT]
cinode teams get <team-id>
cinode teams members list <team-id>
cinode teams skills <team-id>          # cinode.ops.team_skills
cinode keywords search <term>
cinode schema [<model>]                # JSON Schema for output models
```

`<user>` is a numeric id or `me`.

### Output contract

- **stdout is data only.** By default each command writes one JSON document:
  an array for `list` and `search`, an object for `get`. `--jsonl` writes one
  object per line. The shape is the model's `model_dump(mode="json")`, the same
  one `cinode schema` describes. `--raw` writes Cinode's payload untouched.
- **stderr carries errors and progress.** A failure writes one JSON object:
  `{"error": {"type": "ForbiddenError", "status": 403, "path": "...",
  "message": "...", "correlation_id": "..."}}`. Progress lines are written only
  when stderr is a TTY, so an agent's captured stderr holds nothing but errors.
- **Exit codes are part of the contract:**

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | other error |
| 2 | usage error |
| 3 | auth |
| 4 | forbidden |
| 5 | not found |
| 6 | rate limited |

- `teams skills` exits 0 even when members were skipped. Skipped members appear
  in the output's `skipped` array.
- `--match` on `teams list` is a case-insensitive substring filter applied on
  the client side. It exists because the list holds 478 teams and an agent's
  context is limited; anything more complex belongs in `jq`.
- `--table` output for humans is planned, not in v1.

## Extending

Rules for growth that keep existing callers working:

1. A new area of the API gets a new resource module and a new model module,
   wired in as a new attribute on `Cinode` or on a parent resource. Existing
   classes change only by gaining attributes.
2. Fields, methods, CLI commands and CLI flags may be added. Renaming or
   removing any of them is a breaking change.
3. Adding an optional model field is not breaking. Changing a field's type or
   meaning is.
4. Anything that combines several endpoints goes into `ops`, never into a
   resource.
5. An async client, if it is ever needed, gets an `AsyncTransport` and async
   resource classes behind `AsyncCinode`. The models and path building are
   shared.
6. Versioning follows semver. While the version is 0.x, minor versions may
   break; each break is recorded in `CHANGELOG.md`.

Areas likely to come next, in rough order: user profiles and resumes, user
roles, team managers, keyword lookups.

## Data handling

Everything the client reads about colleagues (names, emails, self-assessed
levels) is personnel data.

- `.gitignore` excludes `data/`, `*.csv` and JSON dumps from the first commit.
- Test fixtures are synthetic, shaped like real responses. They contain no real
  colleagues.
- Live tests read only the account owner's own data, plus team membership, and
  write nothing to disk.
- The library never writes files. The CLI writes only to stdout.

## Testing

Tests are few and deliberate. A test exists when it pins behaviour that the
design depends on or that has already been shown to go wrong; it is not written
for coverage. The default run (everything but `live`) finishes in **under two
seconds**: no real sleeps (clocks are injected) and no network (`respx` stands
in for Cinode).

What earns a unit test:

- **Transport:** refresh-once on 401, 429 and 5xx retries, status-to-error
  mapping, bodies that are not JSON, GET-only.
- **Tokens:** caching, refresh near expiry, local-clock lifetime.
- **Models:** the mapping of a real-shaped skill payload, including
  `level: 0` → `None`, and `TeamMember`'s user id resolution.
- **Resources and ops:** `me` resolution, keyword encoding, 403/404 skipping in
  `team_skills`.
- **CLI:** the exact JSON output shape, the error envelope and the exit codes.

Everything else is covered by the live acceptance suite, which exercises the
whole stack.

### Acceptance: the CLI drives the live API

The acceptance suite runs the installed `cinode` command as a subprocess, so
each test exercises CLI → library → transport → Cinode, and pipes the output
through `jq`. It uses the account owner's own profile as test data. Every
assertion is about a fact that does not change when the profile is edited in
normal use:

| Command | Assertion |
|---|---|
| `cinode whoami` | `.user_id == $CINODE_TEST_USER_ID` |
| `cinode users get me` | `.id` matches; `.full_name` is non-empty |
| `cinode users skills list me` | contains `keyword_id == 22070` (Python) with `synonym_id == 2930`; every element validates against the `Skill` model |
| `cinode users skills get me 22070` | `.name == "Python"` |
| `cinode keywords search python` | contains `id == 22070` |
| `cinode teams members list 9873` | contains the owner |
| `cinode users skills list 1` (or another unreadable id) | exit code 4 or 5, error JSON on stderr |
| `cinode teams skills 9873` | *slow*: every member is in `members` or `skipped`; the owner is in `members` |

The ids default to the author's (user 158773, team 9873, keyword 22070 "Python"
with synonym 2930) and can be overridden with `CINODE_TEST_USER_ID`,
`CINODE_TEST_TEAM_ID`, `CINODE_TEST_KEYWORD_ID`, `CINODE_TEST_KEYWORD_NAME`,
`CINODE_TEST_SYNONYM_ID` and `CINODE_TEST_UNREADABLE_USER_ID`, so a colleague can
run the suite against their own profile.

**Parity** (slow, skipped unless the reference script is present). Run
`cinode teams skills 9873` and `~/code/sandbox/cinode-helper/fetch-team-skills.py 9873`,
project both through `jq` to sorted `{user_id, skills: [{keyword_id, level}]}`
(ours maps `null` levels to 0), and compare. Equal means the same data.

## Tooling

- Python 3.14, packaged with `uv`, `src/` layout, console script `cinode`.
- Runtime dependencies: `httpx`, `pydantic`, `typer`, all at their latest
  versions.
- Development dependencies: `pytest`, `respx`, `ruff` (lint and format),
  `pyright` (strict).
- Markers: `live` and `slow`, both excluded by default.
