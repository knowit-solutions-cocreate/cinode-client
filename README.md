# cinode-client

A read-only Python library and CLI for the [Cinode](https://www.cinode.com/) API,
meant for agents first and humans second.

It is **read-only by construction**: the transport can only issue GET, so there
is no write path to enable by mistake. Version 0.1 covers skills, plus the
users, teams and keywords needed to reach them. Version 0.2 adds user
profiles (the data behind a CV) and resumes. See
[`docs/design.md`](docs/design.md) for the design,
[`docs/roadmap.md`](docs/roadmap.md) for what comes next, and
[`docs/plans/`](docs/plans/) for the plans of released versions.

## Install

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install .        # a `cinode` command on PATH
uv tool install -e .     # the same, editable, for working on the code
```

An installed `cinode` writes nothing but its own output. `uv run cinode …` also
works from a checkout, but uv may print messages of its own on stderr.

## Credentials

The client runs as the Cinode user who owns an API account, and can read exactly
what that user can read. Create an API account in Cinode, then set either the
pair:

```sh
export CINODE_ACCESS_ID=...        # the full AccessId, including .app.cinode.com
export CINODE_ACCESS_SECRET=...
```

or a single Basic credential:

```sh
export CINODE_BASIC=$(printf '%s:%s' "$CINODE_ACCESS_ID" "$CINODE_ACCESS_SECRET" | base64)
```

- The AccessId ends in `.app.cinode.com`. Copying only the hex part gives a 400
  at `/token`.
- If both the pair and `CINODE_BASIC` are set, the pair wins. Setting only one
  of the pair is an error.
- `CINODE_TIMEOUT` sets the request timeout in seconds (default 30).
- The company id and user id are never configured; they come from the token.

Secrets are never logged and never shown in `repr`.

## Library

```python
from cinode import Cinode, ForbiddenError
from cinode.ops import team_skills

with Cinode.from_env() as c:              # or Cinode(access_id=..., access_secret=...)
    me = c.users.get("me")                # User
    skills = c.users.skills.list("me")    # list[Skill]
    rated = [s for s in skills if s.is_rated]

    python = c.keywords.search("python")  # list[Keyword]
    teams = c.users.teams.list("me")      # list[Team]

    profile = c.users.profile.get("me")   # Profile
    resumes = c.users.resumes.list("me")  # list[ResumeSummary]
    resume = c.users.resumes.get("me", resumes[0].id)  # Resume, with .blocks

    result = team_skills(c, teams[0].id)  # TeamSkills
    result.members                        # list[MemberSkills(user, skills)]
    result.skipped                        # list[Skipped(user, reason)]

    try:
        c.users.skills.list(1)
    except ForbiddenError as error:
        print(error.status, error.path)
```

A user is a positive `int` or `"me"`. Every call returns a frozen pydantic model
with our snake_case field names; `.raw` holds Cinode's payload. An unrated skill
has `level` `None`, not 0. A 403 is normal: it depends on whose data is asked
for, and `team_skills` records such members in `skipped` rather than failing.

Errors derive from `CinodeError` (with `status`, `path`, `correlation_id`):
`AuthError`, `ForbiddenError`, `NotFoundError`, `RateLimitedError`,
`BadRequestError`, `ServerError` and `UnexpectedResponseError`. Token refresh,
rate limiting and retries are handled inside the client.

## CLI

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
cinode teams skills <team-id>
cinode keywords search <term>
cinode schema [<model>]
```

`<user>` is a numeric id or `me`. `--jsonl` writes a list as one object per
line (every command but `schema`), and `--raw` writes Cinode's payload
untouched (every command but `teams skills` and `schema`). `cinode schema`
lists the output models, and `cinode schema skill` prints one model's JSON
Schema.

```sh
cinode users skills list me | jq '[.[] | select(.is_rated)] | length'
cinode teams list --match cocreate | jq '.[].id'
```

### Output contract

- **stdout is data only:** one JSON document (an array for `list` and `search`,
  an object for `get`), or JSON Lines with `--jsonl`. The shape is what
  `cinode schema` describes.
- **stderr carries errors and progress.** A failure writes one JSON object:

  ```json
  {"error": {"type": "ForbiddenError", "status": 403, "path": "...", "message": "...", "correlation_id": "..."}}
  ```

  Usage errors (exit 2) use the same envelope, with `"type": "UsageError"` and
  `status`, `path` and `correlation_id` all `null`, and no rich box drawing.
  The one exception is a group given no subcommand, which prints its help.
  Progress is written only when stderr is a terminal.
- `teams skills` exits 0 even when members were skipped; they are listed in
  its `skipped` array.
- `users resumes list` gives an empty list, not a 403, for a user whose data
  you cannot read, so an empty list means no resumes, or no access.
  `users profile get` tells the two apart.
- `--match` on `teams list` is a case-insensitive substring filter, applied on
  the client side. Anything more complex belongs in `jq`.
- `--table` output for humans is planned, not in v1.

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | other error |
| 2 | usage error |
| 3 | auth |
| 4 | forbidden |
| 5 | not found |
| 6 | rate limited |

## Tests

```sh
uv run pytest                  # unit tests, no network, under two seconds
uv run ruff check
uv run ruff format --check
uv run pyright
```

The live acceptance suite runs the `cinode` command against the real API, using
the account owner's own profile. It needs credentials and `jq`, and never runs
in CI:

```sh
CINODE_LIVE_TESTS=1 uv run pytest -m live
```

The ids it checks default to the author's. To run it against your own profile,
set `CINODE_TEST_USER_ID`, `CINODE_TEST_TEAM_ID`, `CINODE_TEST_KEYWORD_ID`,
`CINODE_TEST_KEYWORD_NAME`, `CINODE_TEST_SYNONYM_ID` and
`CINODE_TEST_UNREADABLE_USER_ID`.

**Never run the live suite with `pytest -l` or `--showlocals`.** The tests keep
live output out of their failure messages, but those flags print local
variables, which hold it.

## Data handling

Everything the client reads about colleagues (names, emails, self-assessed
levels) is personnel data.

- The library never writes files; the CLI writes only to stdout.
- Test fixtures are synthetic. Live tests read only the owner's own data and
  team membership, and write nothing to disk.
- Never commit live output, or paste it into an issue or pull request. `data/`,
  `*.csv` and JSON dumps are git-ignored.

## How this was built

Every change in this repository was written, reviewed and fixed by Claude
agents, one pull request per plan task, with a main session orchestrating and
merging. [`CLAUDE.md`](CLAUDE.md) holds the workflow.

## Licence

MIT. See [`LICENSE`](LICENSE).
