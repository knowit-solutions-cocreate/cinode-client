# cinode-client — roadmap

What each version holds, one line each. A version gets a detailed plan in
[`docs/plan.md`](plan.md) when work on it starts; at its release, that plan is
archived under [`docs/plans/`](plans/).

| Version | Status | Content |
|---|---|---|
| **v0.1** | Released 2026-09-23 ([plan](plans/v0.1.md), [release](https://github.com/knowit-solutions-cocreate/cinode-client/releases/tag/v0.1.0)) | Transport, skills, users, teams, keywords, `team_skills`, CLI, live acceptance suite |
| **v0.2** | Released 2026-09-24 ([plan](plans/v0.2.md), [release](https://github.com/knowit-solutions-cocreate/cinode-client/releases/tag/v0.2.0)) | User profiles and resumes (`users.profile.get`, `users.resumes.list/get`, `ops.team_profiles`) |
| **v0.3** | In progress ([plan](plan.md)) | Credentials file: `cinode init`, `cinode config show`; `Cinode()` resolves arguments, environment, file (`from_env` removed) |
| v0.4 | Later | Output for humans (`--table`); more reads as needed: user roles, team managers, keyword lookups |
| — | Separate project | MCP server, depending on `cinode-client>=0.1` |
| later | If needed | `AsyncCinode`, only if the MCP server needs concurrency |
