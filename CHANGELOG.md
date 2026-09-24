# Changelog

All notable changes to this project are recorded here. The project follows
semantic versioning; while the version is 0.x, minor versions may break.

## Unreleased

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
