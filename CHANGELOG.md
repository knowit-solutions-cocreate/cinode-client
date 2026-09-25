# Changelog

All notable changes to this project are recorded here. The project follows
semantic versioning; while the version is 0.x, minor versions may break.

## Unreleased

- **Breaking:** `--raw` and `--jsonl` are removed; use `--format raw` and
  `--format jsonl`. Raw output one object per line goes with them:
  `--format raw` always writes one JSON document, and `jq -c '.[]'` splits a
  list. `--format` is the only output option, and each command's `--help`
  lists the formats it takes; any other is a usage error. `init` and
  `config show` take `--format json`.

## 0.3.0 — 2026-09-24

Credentials set up once: `cinode init` saves them to a private credentials
file, which the CLI and the library read when the environment has none.

- **Breaking:** `Cinode.from_env()` is removed; use `Cinode()`, which reads
  the environment whenever no credentials are passed.
- **Credentials file:** `Cinode()` and the CLI read `access_id` and
  `access_secret` from `~/.config/cinode/credentials.toml` (or
  `$XDG_CONFIG_HOME/cinode/credentials.toml`, or `$CINODE_CREDENTIALS_FILE`)
  when the environment holds no credentials. The environment wins as a whole.
- `Cinode(access_id, access_secret)` now honours `CINODE_BASE_URL` and
  `CINODE_TIMEOUT` when `base_url` and `timeout` are not passed.
- **`cinode config show`** reports where the credentials in use come from,
  the AccessId, and the credentials file's path, existence and permissions,
  without a network call. `cinode schema` gains `config`.
- **`cinode init`** checks credentials with `whoami()` and saves them to the
  credentials file, created with mode `0600` and written atomically. It takes
  them from prompts on a terminal, from `--access-id` and the first line of
  stdin otherwise, or from the environment with `--from-env`. Rejected
  credentials are not saved, and an existing file is replaced only with
  `--force`. `cinode schema` gains `init`.

## 0.2.0 — 2026-09-24

User profiles and resumes, as lean, typed projections of Cinode's payloads.

- Licensed under the MIT licence.
- **Profiles and resumes:** `users.profile.get`, `users.resumes.list` and
  `users.resumes.get`, with the lean `Profile`, `ResumeSummary` and `Resume`
  models, and the commands `cinode users profile get`, `cinode users resumes
  list` and `cinode users resumes get`. `cinode schema` gains `profile`,
  `resume` and `resume-summary`. An empty resume list can mean no access.
- **Team profiles:** `cinode.ops.team_profiles` fetches every member's lean
  `Profile`, recording members it may not read in `skipped`, as
  `team_skills` does. It is also `cinode teams profiles`, and `cinode schema`
  gains `team-profiles`.

## 0.1.0 — 2026-09-23

The first release: a read-only library and CLI for Cinode skills, and the
users, teams and keywords needed to reach them.

- **Library:** `Cinode` with `whoami()`, `users` (`list`, `get`, `skills.list`,
  `skills.get`, `teams.list`), `teams` (`list`, `get`, `members.list`) and
  `keywords.search`. A user is a positive `int` or `"me"`.
- **Operations:** `cinode.ops.team_skills` fetches every member's skills, and
  records members that return 403 or 404 in `skipped`.
- **Models:** frozen pydantic models with snake_case fields and `.raw`; an
  unrated skill level (0) becomes `None`.
- **Transport:** GET only. The token is cached and refreshed before expiry and
  once on a 401; `/token` and other endpoints are rate-limited on the client;
  429, 502, 503, 504 and network errors are retried.
- **Errors:** `CinodeError` and its subclasses, with `status`, `path` and
  `correlation_id`.
- **CLI:** `cinode` mirrors the library, plus `teams list --match` and
  `cinode schema`. JSON on stdout, a JSON error envelope on stderr, and
  documented exit codes.
- **Tests:** unit tests, and a live acceptance suite.
