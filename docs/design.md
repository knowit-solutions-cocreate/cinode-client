# cinode-client — design

A read-only Python library for the Cinode API, and a CLI over it. Agents are the
first audience: the library is meant to be wrapped by an MCP server (a separate,
later project), and the CLI is meant to be driven by chat agents. Humans come
second.

Version 0.1 covers skills, plus the users, teams and keywords needed to reach
them. Version 0.2 adds user profiles (the CV data) and resumes. Version 0.3
adds a credentials file, written by `cinode init`. Version 0.4 adds tables
for humans, and puts every output choice behind one `--format` option. The structure
is built so the rest of the API can be added without breaking what is already
there.

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
- **User roles.** `GET users/{u}/roles` returns project-assignment roles,
  and needs the CompanyManager access level and the Assignments module. It
  returns 403 for the owner's own id and for other members (verified
  2026-09-25), as does the company-level `managers`.
- **Keyword lookup by id.** There is no such endpoint: `keywords/{id}`,
  `keywords/synonyms/{id}` and `keywords` all return 404 (verified
  2026-09-25). `keywords.search` is the only keyword read.
- **Choosing a profile translation.** No parameter or path selects one. The
  profile returns the texts that exist, labelled by language, and the caller
  picks. See *Profiles and resumes*.
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

### Profiles and resumes

Verified against the live API on 2026-09-24, across one team's 56 members (50
readable). The spec is wrong about resumes in two ways, noted below.

- **`users/{u}/profile`** (`CompanyUserProfileFullModel`) is large: about
  500 KB for a median profile, 1.6 MB at most. It holds nine section arrays
  (`workExperience`, `education`, `languages`, `skills`, `employers`,
  `training`, `references`, `extSkills`, `commitments`) and a `presentation`.
  Its `skills` hold the same keywords and levels as `users/{u}/skills`, each
  with change history and synonyms added (325 KB against 68 KB), and every
  work experience repeats its skills in full. In those nested skills, as in
  `users/{u}/skills`, `id` is the keyword id (it equals `keyword.id` in all
  72 checked).
- **Translations.** The texts of a section element sit in its `translations`
  array, one entry per language that has text for it, each with a
  `profileTranslationId` and the language at
  `profileTranslation.languageBranch.language.culture` (`"sv-SE"`, always
  populated, and distinct within an element). 41 of 50 profiles have two or
  more translations. Elements then hold one or two entries: fewer than the
  profile's translations when a language has no text, and never more than
  two, even in profiles with three or four. Empty strings occur inside
  entries (`personalDescription: ""`), as well as nulls.
- **Employers** (41 of 50 profiles, 169 elements): `startDate`, `endDate`
  (null when current), `isCurrent`, and texts `name`, `title` and
  `description` in `translations`.
- **Training** (35 of 50 profiles, 170 elements): `trainingType` (0 course,
  1 certification, from the spec's prose enum), `year`, `expireDate` and
  `code` at the top level; `title`, `description`, `issuer` and `supplier` in
  `translations`. There are no start or end dates.
- `references`, `extSkills` and `commitments` are used by few profiles, and
  loosely: `commitments` held publications and `extSkills` free-form notes on
  the profiles seen.
- **`users/{u}/resumes`** lists a user's resumes, with metadata only
  (`CompanyUserResumeBaseModel`, about 1 KB each).
- **`users/{u}/resumes/{id}` returns the content too**, which the spec does not
  say: a `resume` object (about 320 KB) holding around 70 keys of template and
  PDF settings, `blocks`, and each block again under a named key. The
  `resumes/{id}/dynamic` path from the spec returns 404.
- **Resume blocks are template-driven.** Each has a string `blockId`, an int
  `blockType` with no enum in the spec, a `friendlyBlockName`, a `heading`, an
  `order`, and either a `data` list of items or its content inline (`title`,
  `description`, `personalDescription`, `text`). The item shapes vary by block
  type, and item ids are strings.
- **Permissions match skills.** The users whose skills return 403 also return
  403 on their profile. But `resumes` returns **200 with an empty list** for
  them, so no access looks the same as no resumes.
- **Dates** come without a timezone. Profile and resume timestamps carry six
  or seven fractional digits, which pydantic truncates to microseconds.

## Architecture

```
CLI (typer)        cinode users skills list me
   │
Library API        Cinode ── .users ── .skills / .teams / .profile / .resumes
   │                      ── .teams ── .members
   │                      ── .keywords
   │               cinode.ops.team_skills(...) / team_profiles(...)
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
  _config.py           credentials and settings from args, environment or credentials file
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
    profiles.py        Profile and its sections
    resumes.py         ResumeSummary, Resume, ResumeBlock
  resources/
    _base.py           Resource base, UserRef resolution, id checks
    users.py           Users, UserSkills, UserTeams, UserProfile, UserResumes
    teams.py           Teams, TeamMembers
    keywords.py        Keywords
  ops/
    _members.py        walk_members(), the shared loop over a team's members; Skipped
    team_skills.py     team_skills(), TeamSkills
    team_profiles.py   team_profiles(), TeamProfiles
  cli/
    __init__.py        typer app, entry point
    _output.py         --format, JSON/JSONL/raw emitting, error envelope, exit codes
    _table.py          --format table and --columns: column paths, defaults, rich rendering
    config.py          `cinode init` (the only code that writes a file) and `cinode config show`
    users.py  teams.py  keywords.py  schema.py
```

Modules whose names start with an underscore are private. The public surface is
what `cinode/__init__.py`, `cinode.models`, `cinode.errors` and `cinode.ops`
export.

## Library API

```python
from cinode import Cinode

c = Cinode()                              # environment, else the credentials file
c = Cinode(access_id="...", access_secret="...")

c.company_id                              # from the JWT
c.whoami()                                # -> WhoAmI

c.users.list()                            # -> list[UserSummary]
c.users.get(user)                         # -> User
c.users.skills.list(user)                 # -> list[Skill]
c.users.skills.get(user, keyword_id)      # -> Skill
c.users.teams.list(user)                  # -> list[Team]
c.users.profile.get(user)                 # -> Profile
c.users.resumes.list(user)                # -> list[ResumeSummary]
c.users.resumes.get(user, resume_id)      # -> Resume

c.teams.list()                            # -> list[Team]
c.teams.get(team_id)                      # -> Team
c.teams.members.list(team_id)             # -> list[TeamMember]

c.keywords.search(term)                   # -> list[Keyword]

from cinode.ops import team_profiles, team_skills
team_skills(c, team_id)                   # -> TeamSkills
team_profiles(c, team_id)                 # -> TeamProfiles
```

Wherever a user is expected, the argument is a `UserRef = int | Literal["me"]`,
and `"me"` resolves to the token's `sub`. `UserRef` is a plain `TypeAlias`, so
`typing.get_args(UserRef)` gives `(int, Literal["me"])`.

Ids are checked before any request, because callers such as an MCP server pass
values an agent supplied, and type hints do nothing at run time. A user ref must
be exactly `"me"` or a positive `int` that is not a `bool`; digit strings such
as `"158773"` are rejected, and the CLI converts its arguments before calling.
Every other id (`keyword_id`, `team_id`, `resume_id`) must be a positive `int` that is not a
`bool`. A keyword search term must be a `str`; it is stripped, and a term that
is then empty or made only of dots (`.`, `..`) is rejected, since httpx would
collapse it as a dot segment and reach a different endpoint. Anything else
raises `ValueError`.

`Cinode` is a context manager and owns its `httpx.Client`:
`with Cinode() as c: ...`.

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
| `users.profile.get(u)` | `users/{u}/profile` | `CompanyUserProfileFullModel` |
| `users.resumes.list(u)` | `users/{u}/resumes` | `CompanyUserResumeBaseModel[]` |
| `users.resumes.get(u, r)` | `users/{u}/resumes/{r}` | `CompanyUserResumeBaseModel` plus `resume` (see *Profiles and resumes*) |
| `teams.list()` | `teams` | `TeamModel[]` |
| `teams.get(t)` | `teams/{id}` | `TeamModel` |
| `teams.members.list(t)` | `teams/{t}/members` | `TeamMemberModel[]` |
| `keywords.search(q)` | `keywords/search/{term}` | `KeywordModel[]` |
| `whoami()` | `/_whoami` (outside `v0.1`) | `WhoAmIResponseModel` |

`users.resumes.list(u)` passes Cinode's answer through. For a user whose data
the owner cannot read, that is an empty list, not a 403, so an empty list means
"no resumes, or no access". The library does not probe to tell them apart; a
caller that needs to know calls `users.profile.get(u)` or
`users.skills.list(u)`, which raise `ForbiddenError`. The docstring and the CLI
help say so.

### Operations

`cinode.ops` holds functions that combine several calls. They are kept apart
from resources so that resources stay one-to-one with endpoints.

```python
result = team_skills(c, 9873, on_progress=None)
result.team        # Team
result.members     # list[MemberSkills(user: UserSummary, skills: list[Skill])]
result.skipped     # list[Skipped(user: UserSummary, reason: "forbidden" | "not_found")]
```

```python
result = team_profiles(c, 9873, on_progress=None)
result.team        # Team
result.members     # list[MemberProfile(user: UserSummary, profile: Profile)]
result.skipped     # list[Skipped], as for team_skills
```

Both walk the same loop, in `ops/_members.py`: the team is fetched, members
are deduplicated by user id in first-seen order (preferring an entry with the
user inline), and one call is made per member. A 403 or 404 on one member is
recorded in `skipped` and never ends the run. Other errors do end it.
`on_progress(done, total, entry)` is an optional callback, given the entry
just recorded; the library does no printing of its own.

`team_profiles` exists because every team-level question about profiles
(who is placed where, who has worked with what) needs it. Its result is the
lean `Profile` per member: about 1 MB for a 50-person team, against about
25 MB raw. It makes one profile request per member, in sequence.

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
  private attribute, exposed as `.raw`. Callers and the CLI (`--format raw`) can reach
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

### Profile

`Profile` is a lean projection of `CompanyUserProfileFullModel`. It types the
sections that were verified live and leaves out the rest, which `.raw` still
holds. Adding a section later is an added field, so it breaks nothing.

| Field | Source | Notes |
|---|---|---|
| `id: int` | `id` | the profile's id |
| `user_id: int \| None` | `companyUserId` | |
| `language: str \| None` | `profileTranslation.languageBranch.language.culture` | the profile's default translation, `"sv-SE"` |
| `created: datetime \| None` | `createdWhen` | |
| `updated: datetime \| None` | `updatedWhen` | |
| `presentation: Presentation \| None` | `presentation` | |
| `work_experience: list[WorkExperience]` | `workExperience` | null → `[]` |
| `education: list[Education]` | `education` | null → `[]` |
| `languages: list[ProfileLanguage]` | `languages` | null → `[]` |
| `employers: list[Employer]` | `employers` | null → `[]` |
| `training: list[Training]` | `training` | null → `[]` |

**Left out, on purpose:** the profile's `skills` (the same data as
`users.skills.list`, at five times the size), and `references`, `extSkills`
and `commitments`, which few profiles use and whose meaning varies.

**Translations stay as lists.** Each element that has texts keeps a
`translations: list[...]` with one entry per language that has text, in
Cinode's order, never flattened and never filled in. Every text entry has
`profile_translation_id: int | None` (`profileTranslationId`) and
`language: str | None` (`profileTranslation.languageBranch.language.culture`),
plus its own texts. Texts are passed through as they come: an empty string
stays `""` and a null stays `None`; callers treat both as missing.

**Types.** Every `id` is a required `int`, as for every entity. Text fields
(titles, descriptions, names, `culture`, `language`) are `str | None` unless
the table says otherwise, and other ids (`language_id`,
`profile_translation_id`) are `int | None`.

- `Presentation`: `id`, `translations: list[PresentationText]`.
  `PresentationText` adds `title`, `description` and `personal_description`
  (`personalDescription`).
- `WorkExperience`: `id`, `start_date` and `end_date` (`datetime | None`;
  `endDate` is null for a current one), `is_current: bool` (null → `False`),
  `translations: list[WorkExperienceText]` and `skills: list[SkillRef]`.
  `WorkExperienceText` adds `employer`, `title` and `description`.
- `SkillRef`: `keyword_id: int` (`id`, else `keyword.id`, as for `Skill`) and
  `name: str` (`keyword.masterSynonym`, null → `""`). A work experience's
  skills are reduced to this reference; `users.skills.get` has the rest.
- `Education`: `id`, `start_date`, `end_date`,
  `translations: list[EducationText]`. `EducationText` adds `school_name`
  (`schoolName`), `program_name` (`programName`), `degree` and `description`.
- `ProfileLanguage`: `id`, `language_id` (`language.languageId`), `name`
  (`language.name`), `culture` (`language.culture`), `level: int | None`.
  The level scale is not documented and is passed through as it comes.
- `Employer`: `id`, `start_date`, `end_date`, `is_current: bool` (null →
  `False`), `translations: list[EmployerText]`. `EmployerText` adds `name`,
  `title` and `description`.
- `Training`: `id`, `training_type: int | None` (`trainingType`, an open enum:
  0 course, 1 certification), `year: int | None`, `expires: datetime | None`
  (`expireDate`), `code`, `translations: list[TrainingText]`. `TrainingText`
  adds `title`, `description`, `issuer` and `supplier`.

Null translation and skill arrays become `[]`, as the sections do.

### Resumes

- `ResumeSummary` (one per `resumes` element): `id`, `user_id`
  (`companyUserId`), `title`, `description`, `language` (`language.culture`),
  `template_id` (`template.id`), `template_name` (`template.title`), `created`
  (`created.time`), `updated` (`updated.time`), `is_public: bool` (null →
  `False`), `profile_translation_id`, `view_url` (`viewUrl`) and
  `public_view_url` (`publicViewUrl`). `template_id` and
  `profile_translation_id` are `int | None`, `created` and `updated` are
  `datetime | None`, and the texts and URLs are `str | None`.
- `Resume(ResumeSummary)`: adds `blocks: list[ResumeBlock]` from
  `resume.blocks`, in Cinode's order (null → `[]`). The template and PDF
  settings, and the blocks repeated under named keys, are left out; `.raw`
  holds them.
- `ResumeBlock`: `block_id: str` (`blockId`), `block_type: int | None`
  (`blockType`, an open enum like `keyword_type`), `name: str | None`
  (`friendlyBlockName`), `heading: str | None`, `order: int | None`, the
  inline texts
  `title`, `description`, `personal_description` and `text` (all
  `str | None`, set only on blocks that carry their content inline), and
  `items: list[dict[str, Any]]` from `data` (null → `[]`).

**Block items are passed through untouched.** Their shape depends on the block
type and the template, and no enum names the types, so typing them would be
guesswork checked against one account. They are the one place where output
keeps Cinode's camelCase keys. `block_id` is required like any entity id, and
an item that is not an object fails the parse; both were true of every block
seen, and a resume that breaks them raises `UnexpectedResponseError` rather
than being half read. Typing an item kind later would change `items`'
type, which is breaking, so it would come as a new field beside `items`.

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

| Setting | Argument | Environment | Credentials file |
|---|---|---|---|
| credentials | `access_id`, `access_secret` | `CINODE_ACCESS_ID` + `CINODE_ACCESS_SECRET`, or `CINODE_BASIC` | `access_id`, `access_secret` |
| credentials file location | `credentials_file` | `CINODE_CREDENTIALS_FILE` | |
| base URL | `base_url` | `CINODE_BASE_URL` (tests only) | |
| timeout | `timeout` | `CINODE_TIMEOUT` | |

The company id and user id are never configured; they come from the token.
Secrets are never logged and never shown in `repr`.

### Where credentials come from

There is one way to build a client, and it resolves every setting in the
same order: **arguments, then the environment, then the credentials file,
then the default.**

```python
Cinode(
    access_id: str | None = None,
    access_secret: str | None = None,
    *,
    base_url: str | None = None,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,     # default: os.environ
    credentials_file: Path | None = None,     # default: see Location below
)
```

The CLI calls `Cinode()`, and so should the MCP server. This is the convention
of `Anthropic()`, `OpenAI()` and `boto3.client()`, which read their
environment when no key is passed. v0.1's `Cinode.from_env()` is removed:
`Cinode()` does the same whenever the environment holds credentials.

- **Credentials:** `access_id` and `access_secret` together are used as
  given, and neither the environment nor the file is read for credentials.
  Passing only one of them raises `ValueError`, like any other bad argument.
  Given neither, the environment is read, then the file.
- **Base URL and timeout:** the argument, else `CINODE_BASE_URL` or
  `CINODE_TIMEOUT`, else the default, whichever source the credentials came
  from. The file holds neither.
- `env` stands in for `os.environ` (tests pass a mapping), and
  `credentials_file` for the file's default location.

Between the environment and the file, **the environment wins as a whole.** If it holds
credentials (the pair, or `CINODE_BASIC`), the file is not opened, so a broken
file cannot break a caller who sets the environment. Half a pair is still an
error and never falls back to the file, which may belong to another account.
With no credentials in either, `Cinode()` raises `AuthError`: "No Cinode
credentials: none in the environment, and no file at `<path>`. Run
`cinode init`, or set …".

### The credentials file

- **Location:** `$CINODE_CREDENTIALS_FILE` if set (a file path, `~` expanded), else
  `$XDG_CONFIG_HOME/cinode/credentials.toml` if `XDG_CONFIG_HOME` is an absolute
  path, else `~/.config/cinode/credentials.toml`, on macOS as elsewhere.
- **Format:** TOML with two flat, top-level string keys, and nothing else
  read:

  ```toml
  # Written by `cinode init`. It holds a secret: keep it private (chmod 600).
  access_id = "0123abcd.app.cinode.com"
  access_secret = "..."
  ```

  Unknown keys are ignored, so a file written by a later version still loads,
  as long as it keeps the two keys.
  A file that cannot be read, is not valid TOML, or lacks either key as a
  non-empty string raises `AuthError`, whose message names the file and the
  key but never a value.
- **The secret is stored in plain text,** protected by file permissions, as
  `gh`, `aws` and `.netrc` do. An OS keychain would add a dependency and fail
  where agents run (headless, over SSH, in containers).
- **Permissions are reported, not enforced.** `cinode init` creates the file
  with mode `0600` and its directory with `0700`. Loading a file that others
  can read neither fails nor prints a warning (stderr is for errors only);
  `cinode config show` reports it.
- **Credentials only.** The file is named for what it holds, which is also
  why it must be private. Settings that are not secret, if any are ever
  added, would go in a separate `config.toml` beside it, which need not be.
- **One account.** Named profiles, if they are ever needed, would be added as
  TOML tables beside the flat keys, which stay the default account.
- `tomllib` reads the file, so there is no new dependency. The library only
  ever reads it; the writer lives in the CLI (see *Data handling*).

### `cinode init`

Checks a set of credentials against Cinode and saves them to the credentials file.

1. If the file exists and `--force` is not given, it fails at once (exit 1)
   and asks for nothing.
2. It takes the credentials from one of three places:
   - `--from-env`: the pair in the environment, or `CINODE_BASIC` decoded and
     split at its first `:`. This is the one-step migration for users who
     export credentials today.
   - On a terminal: `--access-id`, or a prompt, for the AccessId, then a
     hidden prompt for the secret. Prompts are written to stderr.
   - Otherwise (an agent or script): `--access-id ID`, with the secret as the
     first line of stdin.

   The secret is never a command-line option, since arguments show up in
   `ps` and in shell history. These are usage errors (exit 2), raised before
   any request: `--from-env` together with `--access-id`; `--from-env` with
   no usable credentials in the environment; no `--access-id` without a
   terminal; an empty AccessId or secret; and a value with a control
   character, or one that is not valid UTF-8.
3. It verifies them with `whoami()`, a GET like every other call, and honours
   `CINODE_BASE_URL` and `CINODE_TIMEOUT`. If Cinode rejects them, nothing is
   written (exit 3).
4. It writes the file atomically: a temporary file in the same directory,
   created with mode `0600` from the start (never `chmod`ed afterwards), then
   renamed over the target.
5. It prints `{"path", "access_id", "company_id", "user_id"}`.

### `cinode config show`

Reports where the credentials come from, without a network call; `cinode
whoami` is the online check. It resolves credentials exactly as every other
command does, so when there are none, or the file is malformed, it fails the
same way (exit 3), with a message that names the path. On success it prints:

| Field | Type | Meaning |
|---|---|---|
| `source` | `"env" \| "file"` | where the credentials came from |
| `access_id` | `str \| null` | the AccessId in use; decoded from `CINODE_BASIC` when that is the source, `null` if it does not decode |
| `path` | `str` | the credentials file's location, whether or not it was used |
| `file_exists` | `bool` | |
| `file_mode` | `str \| null` | the permission bits as octal, `"0600"`; `null` without a file |
| `file_private` | `bool \| null` | no group or other permission bits set; `null` without a file |

The secret is never part of any output.

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
cinode users profile get <user>
cinode users resumes list <user>
cinode users resumes get <user> <resume-id>
cinode teams list [--match TEXT]
cinode teams get <team-id>
cinode teams members list <team-id>
cinode teams skills <team-id>          # cinode.ops.team_skills
cinode teams profiles <team-id>        # cinode.ops.team_profiles
cinode keywords search <term>
cinode schema [<model>]                # JSON Schema for output models
cinode init [--access-id ID] [--from-env] [--force]
cinode config show
```

`<user>` is a numeric id or `me`. Every command but `schema` also takes
`--format`, and those that take `--format table` take `--columns` (see
*Output contract* and *Tables*).

### Output contract

- **stdout is data only.** Every command but `schema` takes
  `--format FORMAT`, which is the only output option:

  | Format | Output |
  |---|---|
  | `json` (default) | one JSON document: an array for `list` and `search`, an object for `get` |
  | `jsonl` | one JSON object per line; for a single object, the same as `json` |
  | `raw` | Cinode's payload untouched, as one JSON document |
  | `table` | a table for a human to read (see *Tables*) |

  The JSON shape is the model's `model_dump(mode="json")`, the same one
  `cinode schema` describes. JSON is the default whether or not stdout is a
  terminal, so output never depends on where it goes.
- **Not every command takes every format.** A command's `--help` lists the
  formats it takes, and any other is a usage error (exit 2), raised before
  any request:

  | Commands | Formats |
  |---|---|
  | the resource commands under `users`, `teams` and `keywords`, and `whoami` | `json`, `jsonl`, `raw`, `table` |
  | `users profile get`, `users resumes get` | `json`, `jsonl`, `raw` |
  | `teams skills` | `json`, `jsonl`, `table` |
  | `teams profiles` | `json`, `jsonl` |
  | `init`, `config show` | `json`, `table` |

  `raw` is offered only where there is a Cinode payload: the results of
  `teams skills`, `teams profiles`, `init` and `config show` are built, not
  parsed. Profiles, resumes and team profiles are trees with no useful table.
- **stderr carries errors and progress,** whatever the format. A failure writes one JSON object:
  `{"error": {"type": "ForbiddenError", "status": 403, "path": "...",
  "message": "...", "correlation_id": "..."}}`. Usage errors (exit 2) use the
  same envelope, with `"type": "UsageError"` and `status`, `path` and
  `correlation_id` all `null`, and no rich box drawing. The one exception is
  a group given no subcommand, which prints its help. Progress lines are
  written only when stderr is a TTY, so an agent's captured stderr holds
  nothing but errors.
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

- `teams skills` and `teams profiles` exit 0 even when members were skipped.
  Skipped members appear in the output's `skipped` array.
- `--match` on `teams list` is a case-insensitive substring filter applied on
  the client side. It exists because the list holds 478 teams and an agent's
  context is limited; anything more complex belongs in `jq`.
- `--format raw` on `users profile get` and `users resumes get` writes
  Cinode's whole payload, which is hundreds of kilobytes. The default output
  is the lean model.
- The outputs of `init` and `config show` are in `cinode schema` as `init`
  and `config`. `init`'s prompts go to stderr, so stdout still holds only
  its output.

### Tables

`--format table` is for a human at a terminal. The layout of a table is
**not** part of the contract, and may change in any version; agents and
scripts use JSON. What is part of the contract: which commands take `table`,
the column paths `--columns` accepts, and that errors stay JSON on stderr.

- **Rendering.** A `rich.table.Table`, printed by a `rich.console.Console`
  on stdout with highlighting, markup and emoji codes all off: Cinode's text
  is data, so a name holding `[/x]` or `:smile:` is printed as it is. The
  width is `COLUMNS` if set, else the terminal's, else 80, as `rich`
  decides; colour and styles appear only on a terminal. Cells fold rather
  than truncate, so no value is cut short, and the title and caption are
  printed whole, past the width if need be. Every C0 and C1 control
  character in a cell, the title or the caption is replaced by U+FFFD, so
  Cinode's text never reaches the terminal as an escape sequence; a newline
  is kept, and breaks the line as folding does.
- **Rows.** A list is one row per element. A single object (a `get`,
  `whoami`, `init`, `config show`) is a two-column table, *Field* and
  *Value*, with one row per column path. `teams skills` is one row per member
  and skill (see below). An empty list is a table with headers and no rows.
- **Column paths.** A column is a path: field names joined by dots, through
  nested models but not into lists, ending at a scalar (a string, number,
  boolean or date, or `null`). Computed fields count, so `full_name` and
  `years_experience` are columns. `user.full_name` is a column of a team
  member; `blocks` of a resume is not.
- **Cells.** The value at the path in `model_dump(mode="json")`. `null`, or a
  `null` model on the way, is an empty cell; a boolean is `true` or `false`;
  anything else is its string.
- **`--columns PATH[,PATH…]`** replaces the default columns with the paths
  given, in that order; for a single object it picks the rows. Items are
  stripped of spaces. It is a usage error (exit 2), before any request, to
  give `--columns` without `--format table`, to give it empty or with an
  empty item, or to name a path the command's row model does not have; that
  error lists the valid paths, which makes it the way to discover them.
- **Headers.** Each default column has a label. A path given with
  `--columns` keeps its label if it is one of its row model's defaults, and is
  otherwise humanised: dots and underscores become spaces and the first
  letter is capitalised (`user.full_name` → "User full name"). The *Field*
  column of a single object always shows the humanised path, with or
  without `--columns`.

Default columns:

| Row model | Commands | Default columns (label) |
|---|---|---|
| `UserSummary` | `users list` | `id` (Id), `full_name` (Name) |
| `Skill` | `users skills list` | `keyword_id` (Keyword id), `name` (Name), `level` (Level), `level_goal` (Goal), `years_experience` (Years), `favourite` (Favourite) |
| `Team` | `users teams list`, `teams list` | `id` (Id), `name` (Name), `parent_team_id` (Parent) |
| `TeamMember` | `teams members list` | `user_id` (User id), `user.full_name` (Name), `availability_percent` (Availability %) |
| `ResumeSummary` | `users resumes list` | `id` (Id), `title` (Title), `language` (Language), `updated` (Updated) |
| `Keyword` | `keywords search` | `id` (Id), `name` (Name), `type` (Type), `verified` (Verified) |
| `MemberSkillRow` | `teams skills` | `user.id` (User id), `user.full_name` (Name), `skill.keyword_id` (Keyword id), `skill.name` (Skill), `skill.level` (Level), `skill.years_experience` (Years) |

A single object's default rows are all of its column paths, in field order.

**`teams skills`** has the row model `MemberSkillRow(user: UserSummary,
skill: Skill | None)`, which exists only in the CLI and is not in `cinode
schema`. A member with skills has one row per skill, in Cinode's order; a
member with none has one row with empty skill cells. The table's title is the
team's name, and when members were skipped its caption counts them by
reason: "6 members skipped: forbidden 6". Neither the title nor the caption
wraps. When every member is skipped, the table has headers and no rows.

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

Areas likely to come next, in rough order: team managers, and the profile
sections v0.2 leaves out (`references`, `extSkills`, `commitments`).
`teams/{t}/managers` was verified on 2026-09-25: it returned 200 on every team
sampled, `[]` on most, and its elements parse as `UserSummary`.

## Data handling

Everything the client reads about colleagues (names, emails, self-assessed
levels) is personnel data.

- `.gitignore` excludes `data/`, `*.csv` and JSON dumps from the first commit.
- Test fixtures are synthetic, shaped like real responses. They contain no real
  colleagues.
- Live tests read only the account owner's own data, plus team membership, and
  write nothing to disk, except the `cinode init` round trip, which writes a
  credentials file to a temporary directory and deletes it in teardown.
- The library never writes files. The CLI writes only to stdout, except
  `cinode init`, which writes the credentials file. The credentials file holds a
  secret, not personnel data.

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
  `level: 0` → `None`, and `TeamMember`'s user id resolution; the lean
  projections of a profile and a resume, including what they leave out.
- **Resources and ops:** `me` resolution, keyword encoding, 403/404 skipping in
  `team_skills` and `team_profiles`.
- **Configuration:** the precedence between environment and file, the config
  file's location, and malformed files.
- **CLI:** the exact JSON output shape, the error envelope and the exit codes;
  which formats a command refuses; `--columns` validation, and the rows of a
  table (not its layout);
  `cinode init`'s file mode, its verify-before-write and its refusal to
  overwrite.

Unit tests never see the developer's own credentials file: an autouse fixture
points `CINODE_CREDENTIALS_FILE` at a path that does not exist.

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
| `cinode users skills get me 22070 --format raw` | `.keyword.masterSynonym == "Python"` |
| `cinode users skills list me --format table` | exit 0; stdout contains "Python" and is not JSON |
| `cinode users profile get me` | `.user_id` matches; the output validates against `Profile` |
| `cinode users profile get 1` (the unreadable id) | exit code 4 or 5, error JSON on stderr |
| `cinode users resumes list me` | every element's `.user_id` matches |
| `cinode users resumes get me <first id>` | `.id` is that id; `.blocks` is non-empty (skipped if the owner has no resumes) |
| `cinode teams skills 9873` | *slow*: every member is in `members` or `skipped`; the owner is in `members` |
| `cinode teams profiles 9873` | *slow*: the same, with the owner's `.profile.user_id` matching |
| `cinode init --from-env`, then `cinode whoami` with only `CINODE_CREDENTIALS_FILE` set | `.user_id` matches; the file has mode `0600` (needs credentials in the environment; the file is deleted in teardown) |

The ids default to the author's (user 158773, team 9873, keyword 22070 "Python"
with synonym 2930) and can be overridden with `CINODE_TEST_USER_ID`,
`CINODE_TEST_TEAM_ID`, `CINODE_TEST_KEYWORD_ID`, `CINODE_TEST_KEYWORD_NAME`,
`CINODE_TEST_SYNONYM_ID` and `CINODE_TEST_UNREADABLE_USER_ID`, so a colleague can
run the suite against their own profile.

**Parity** was checked once, at 0.1 acceptance, and not kept as a test.
`cinode teams skills 9873` and the reference script
`~/code/sandbox/cinode-helper/fetch-team-skills.py 9873` were projected through
`jq` to sorted `{user_id, skills: [{keyword_id, level}]}` (ours mapping `null`
levels to 0) and compared: every member, keyword id and level matched. The
test was then removed, so the suite does not depend on a script outside the
repository.

## Tooling

- Python 3.14, packaged with `uv`, `src/` layout, console script `cinode`.
- Runtime dependencies: `httpx`, `pydantic`, `typer` and `rich` (for tables; typer
  already depends on it), all at their latest versions.
- Development dependencies: `pytest`, `respx`, `ruff` (lint and format),
  `pyright` (strict).
- Markers: `live` and `slow`, both excluded by default.
