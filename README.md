# cinode-client

A read-only Python library and CLI for the [Cinode](https://www.cinode.com/) API,
meant for agents first and humans second.

It is **read-only by construction**: the transport can only issue GET, so there
is no write path to enable by mistake. Version 0.1 covers skills, plus the
users, teams and keywords needed to reach them. Version 0.2 adds user
profiles (the data behind a CV) and resumes. Version 0.3 adds `cinode init`,
which saves credentials to a credentials file, read when the environment has
none. See
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
what that user can read. Create an API account in Cinode, then save its
credentials once with `cinode init`, which checks them against Cinode
(`whoami`) and writes them to the credentials file:

```sh
cinode init                                   # on a terminal: prompts, the secret hidden
printf '%s\n' "$SECRET" | cinode init --access-id 0123abcd.app.cinode.com   # agents and scripts
cinode init --from-env                        # save what the environment holds today
```

- Prompts go to stderr. Without a terminal, the secret is the first line of
  stdin; it is never a command-line option, since arguments show up in `ps`
  and shell history.
- `--from-env` takes `CINODE_ACCESS_ID` and `CINODE_ACCESS_SECRET`, or
  `CINODE_BASIC` split at its first colon.
- Credentials that Cinode rejects are not saved (exit 3). An existing file is
  replaced only with `--force` (otherwise exit 1).
- On success it prints `{"path", "access_id", "company_id", "user_id"}`,
  never the secret.
- The AccessId ends in `.app.cinode.com`. Copying only the hex part gives a 400
  at `/token`.

### Environment variables

Instead of the file, set either the pair:

```sh
export CINODE_ACCESS_ID=...        # the full AccessId, including .app.cinode.com
export CINODE_ACCESS_SECRET=...
```

or a single Basic credential:

```sh
export CINODE_BASIC=$(printf '%s:%s' "$CINODE_ACCESS_ID" "$CINODE_ACCESS_SECRET" | base64)
```

- If both the pair and `CINODE_BASIC` are set, the pair wins. Setting only one
  of the pair is an error.
- `CINODE_TIMEOUT` sets the request timeout in seconds (default 30), whichever
  source the credentials come from.
- The company id and user id are never configured; they come from the token.

### The credentials file

When the environment holds no credentials, the CLI and `Cinode()` read them
from a credentials file, at `$CINODE_CREDENTIALS_FILE` if set, else
`$XDG_CONFIG_HOME/cinode/credentials.toml` (when `XDG_CONFIG_HOME` is an
absolute path), else `~/.config/cinode/credentials.toml`, on macOS too:

```toml
# Written by `cinode init`. It holds a secret: keep it private (chmod 600).
access_id = "0123abcd.app.cinode.com"
access_secret = "..."
```

- The environment wins as a whole: if it holds any credentials (the pair,
  half a pair, or `CINODE_BASIC`), the file is not opened.
- The secret is stored in plain text, so keep the file private. `cinode init`
  creates it with mode `0600` (and its directory, if new, with `0700`), and
  writes it atomically. Loading a file others can read is not an error.
- A file that cannot be read, is not TOML, or lacks either key as a
  non-empty string is an auth error that names the file and the key.
- `cinode config show` says where the credentials in use come from (`env` or
  `file`), with the AccessId, the file's path, and whether the file exists and
  is private. It makes no request, and never shows the secret; `cinode whoami`
  is the online check.

Secrets are never logged and never shown in `repr`.

## Library

```python
from cinode import Cinode, ForbiddenError
from cinode.ops import team_profiles, team_skills

with Cinode() as c:                       # or Cinode(access_id=..., access_secret=...)
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

    people = team_profiles(c, teams[0].id)  # TeamProfiles
    people.members                        # list[MemberProfile(user, profile)]

    try:
        c.users.skills.list(1)
    except ForbiddenError as error:
        print(error.status, error.path)
```

A user is a positive `int` or `"me"`. Every call returns a frozen pydantic model
with our snake_case field names; `.raw` holds Cinode's payload. An unrated skill
has `level` `None`, not 0. A 403 is normal: it depends on whose data is asked
for, and `team_skills` and `team_profiles` record such members in `skipped`
rather than failing.

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
cinode teams profiles <team-id>
cinode keywords search <term>
cinode schema [<model>]
cinode init [--access-id ID] [--from-env] [--force]
cinode config show
```

`<user>` is a numeric id or `me`. Every command but `schema` takes
`--format` (see *Output contract*).
`cinode schema` lists the output models, and `cinode schema skill` prints one
model's JSON Schema.

```sh
cinode users skills list me | jq '[.[] | select(.is_rated)] | length'
cinode teams list --match cocreate | jq '.[].id'
```

### Output contract

- **stdout is data only.** `--format` picks what is written:

  | Format | Output |
  |---|---|
  | `json` (default) | one JSON document: an array for `list` and `search`, an object for `get` |
  | `jsonl` | one JSON object per line; for a single object, the same as `json` |
  | `raw` | Cinode's payload untouched, as one JSON document |
  | `table` | a table for a human to read (see *Tables*) |

  The JSON shape is what `cinode schema` describes. Not every command takes
  every format: `raw` is refused by `teams skills`, `teams profiles`, `init`
  and `config show`, whose results are built rather than read from Cinode,
  and `jsonl` by `init` and `config show`. `table` is refused by
  `users profile get`, `users resumes get` and `teams profiles`, whose
  results are trees. A command's `--help` lists the formats it takes, and any
  other is a usage error.
- **stderr carries errors and progress,** whatever the format. A failure writes one JSON object:

  ```json
  {"error": {"type": "ForbiddenError", "status": 403, "path": "...", "message": "...", "correlation_id": "..."}}
  ```

  Usage errors (exit 2) use the same envelope, with `"type": "UsageError"` and
  `status`, `path` and `correlation_id` all `null`, and no rich box drawing.
  The one exception is a group given no subcommand, which prints its help.
  Progress is written only when stderr is a terminal.
- `teams skills` and `teams profiles` exit 0 even when members were skipped;
  they are listed in the `skipped` array.
- `users resumes list` gives an empty list, not a 403, for a user whose data
  you cannot read, so an empty list means no resumes, or no access.
  `users profile get` tells the two apart.
- `--match` on `teams list` is a case-insensitive substring filter, applied on
  the client side. Anything more complex belongs in `jq`.

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | other error |
| 2 | usage error |
| 3 | auth |
| 4 | forbidden |
| 5 | not found |
| 6 | rate limited |

### Tables

`--format table` prints a table for a human at a terminal:

```
$ cinode users skills list me --format table
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Keyword id ┃ Name   ┃ Level ┃ Goal ┃ Years ┃ Favourite ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ 22070      │ Python │ 4     │ 5    │ 4.0   │ true      │
└────────────┴────────┴───────┴──────┴───────┴───────────┘
```

A list is one row per element, with a few default columns. A single object
(a `get`, `whoami`, `init`, `config show`) is a *Field* and *Value* table
with one row per field, nested fields included (`user.full_name`). `null`
shows as an empty cell. Cells fold rather than truncate, and the width is `COLUMNS`
if set, else the terminal's.

`teams skills --format table` is one row per member and skill, with the
team's name as its title. A member with no skills has one row with empty
skill cells, and a caption counts the members skipped, by reason:
"6 members skipped: forbidden 6".

Tables are for humans. Their layout may change in any version, so agents
and scripts use JSON. Errors stay JSON on stderr under `--format table`.

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
