# cinode-client — plan for v0.3

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to carry out the tasks in order. Write only the
> tests a task lists; they pin behaviour the design depends on. Do not add
> tests for coverage. Steps use checkboxes for tracking.

**Goal:** v0.3 lets a user or an agent set up credentials once. `cinode init`
checks them and saves them to a credentials file, which the CLI and the library
read whenever the environment has no credentials. `cinode config show` says
where the credentials in use come from.

**Architecture:** no new layers. `_config.py` learns to find and read the
credentials file, and `Cinode(...)` becomes the one way to build a client,
resolving arguments, then the environment, then the file. `Cinode.from_env()`
is removed. The one new CLI module, `cli/config.py`, holds `cinode config
show` and `cinode init`, and with it the only code that writes a file. The
library only reads.

**Tech stack:** unchanged. `tomllib` (stdlib) reads the file, and a few lines
of our own write it. No new dependencies.

**Spec:** [`docs/design.md`](design.md), in particular *Configuration* (with
*Where credentials come from*, *The credentials file*, `cinode init` and `cinode
config show`) and *Data handling*. Read them before starting; this plan does
not repeat them.

## Global constraints

- Everything in v0.2's global constraints still holds: GET only, synthetic
  fixtures (company 99, user 1001), the four checks on every commit, the
  default run under two seconds, and only the tests listed.
- **One deliberate break, and nothing else.** `Cinode.from_env()` is removed,
  which is recorded under a *Breaking* heading in the CHANGELOG. Everything
  else v0.2 shipped keeps working:
  - `Cinode(access_id, access_secret)` behaves as before, except that
    `CINODE_BASE_URL` and `CINODE_TIMEOUT` now apply when `base_url` and
    `timeout` are not passed.
  - The private `Settings.from_env()` is unchanged, and its existing tests
    pass unedited.
  - The CLI behaves as before whenever the environment holds credentials.
    The only visible difference is the text of the "no credentials" message,
    which now names the credentials file; its type and exit code stay the
    same.
- **Tests never touch the real home directory.** Every file a test writes goes
  under `tmp_path`. `CINODE_CREDENTIALS_FILE` or `HOME` is set with `monkeypatch`, never
  left to default.
- **The secret never appears in output:** not on stdout or stderr, not in an
  error message, not in a `repr`, and not in a live test's failure message.
  Test secrets are distinctive strings (for example `"s3cret-value"`) so that
  a test can assert they are absent.
- **Synthetic AccessIds** look like real ones: `"id-1.app.cinode.com"`.

## Review focus

Failure modes the design implies but does not spell out. Each one has a test
in the task named.

1. **The environment wins as a whole.** With credentials in the environment,
   the file is never opened, so even a malformed file is ignored. Half a pair
   raises the existing error and never falls back to the file. *(Task 1)*
2. **Unit tests never read the developer's own credentials file.** Without the
   autouse fixture, `test_no_credentials_is_an_auth_error` would reach a real
   account on any machine where `cinode init` has been run. *(Task 1)*
3. **Error messages about the file name the file and the key, never a
   value.** A malformed file's `AuthError` does not contain the secret.
   *(Task 1)*
4. **The file is private from the moment it exists.** It is created with mode
   `0600` (for example by `tempfile.mkstemp`, which does so), never created
   and then `chmod`ed. Its directory is `0700` when `init` creates it. The
   write is atomic, and no temporary file is left behind on success or
   failure. *(Task 2)*
5. **Verify before write.** Credentials that Cinode rejects leave no file
   behind, and no temporary file either. *(Task 2)*
6. **The writer round-trips any credential.** A secret containing `"`, `\`
   and `:` reads back unchanged through `tomllib`. `--from-env` splits
   `CINODE_BASIC` at the *first* colon, since a secret may contain colons.
   *(Task 2)*
7. **Still GET only.** `init` verifies through `whoami()`. No new request
   method appears anywhere, and the existing GET-only transport test passes
   unedited. *(Task 2)*

## File map

```
src/cinode/
  _config.py        credentials_path, read_credentials, decode_basic, env_options, Settings.resolve
  _client.py        Cinode.__init__ resolves; from_env removed
  cli/  config.py (new)  __init__.py  _output.py  schema.py
tests/
  conftest.py       autouse _no_credentials_file
  cli/conftest.py   patch _output.client instead of Cinode.from_env
  live/conftest.py  no-op _no_credentials_file override; cinode(..., env=...)
  test_config.py  cli/test_cli.py  live/test_acceptance.py
README.md  CHANGELOG.md
```

---

### Task 1: Read credentials from the credentials file, and `cinode config show`

**Files:** `src/cinode/_config.py`, `src/cinode/_client.py`,
`src/cinode/cli/_output.py`, `src/cinode/cli/config.py` (new),
`src/cinode/cli/__init__.py`, `src/cinode/cli/schema.py`,
`tests/conftest.py`, `tests/cli/conftest.py`, `tests/live/conftest.py`,
`tests/test_config.py`, `tests/cli/test_cli.py`, `README.md`,
`CHANGELOG.md`.

**Produces:**
- In `_config.py`:
  - `credentials_path(env: Mapping[str, str] | None = None) -> Path`, following the
    design's *Location* rule. `CINODE_CREDENTIALS_FILE` has `~` expanded, and a
    relative `XDG_CONFIG_HOME` is ignored. `~` and the fallback home come from
    `Path.home()` (that is, `HOME` in `os.environ`), not from `env`. The path
    is never `.resolve()`d, since on macOS that turns `/var` into
    `/private/var` and breaks exact comparisons.
  - `read_credentials(path: Path) -> tuple[str, str] | None`, which gives
    `(access_id, access_secret)`. It returns `None` when there is no file at
    `path`. It raises `AuthError` when the file cannot be read (any `OSError`,
    a directory at the path, or `UnicodeDecodeError`), is not valid TOML, or
    lacks either key as a non-empty `str`. The message names the path
    and the key, never a value, and a `tomllib` error message, which can quote
    the offending line, is not passed through. Unknown keys are ignored.
  - `decode_basic(basic: str) -> tuple[str, str] | None`: drops all
    whitespace (as `from_env` does), base64-decodes the rest and splits it at
    the first `:`. It returns `None` if the value is not valid base64
    (`binascii.Error`, bad padding), does not decode as UTF-8, or has no
    colon. Task 2's `--from-env` uses it
    too.
  - `env_options(env: Mapping[str, str]) -> tuple[str, float]`: the base URL
    and timeout from `CINODE_BASE_URL` and `CINODE_TIMEOUT`, as `from_env`
    reads them today. `from_env` and `resolve` call it.
  - `Settings` gains two fields that are not secret:
    - `source: Literal["argument", "env", "file"] = "argument"`
    - `access_id: str | None = None`

    `from_credentials` gains a keyword-only `source` (default `"argument"`)
    and sets `access_id`. `from_env` sets `source="env"`, and takes
    `access_id` from the pair, or from `decode_basic` when only `CINODE_BASIC`
    is set (`None` if that fails).
  - `Settings.resolve(access_id: str | None = None, access_secret: str | None = None, *, base_url: str | None = None, timeout: float | None = None, env: Mapping[str, str] | None = None, credentials_file: Path | None = None) -> Self`,
    as in the design's *Where credentials come from*:
    - `env` defaults to `os.environ`. `base_url` and `timeout` fall back to
      `env_options(env)`.
    - With both `access_id` and `access_secret`, it builds the settings from
      them (`source="argument"`), and neither the environment nor the file
      is read for credentials. With only one, it raises `ValueError`.
    - If the environment holds credentials, or half a pair, it defers to
      `from_env`, and the file is not opened. "Holds credentials" is exactly
      `from_env`'s own test: a non-empty `CINODE_ACCESS_ID` or
      `CINODE_ACCESS_SECRET`, or a `CINODE_BASIC` that is non-empty once its
      whitespace is dropped. An empty or blank `CINODE_BASIC` counts as
      unset, so the file is tried.
    - Otherwise it reads `read_credentials(credentials_file or credentials_path(env))`
      and builds the settings with `source="file"`.
    - With neither, it raises `AuthError` with a message that begins
      `"No Cinode credentials"` and names the path.
- `Cinode.__init__` takes `Settings.resolve`'s parameters, with the same
  names and defaults, and builds its transport from `Settings.resolve(...)`.
  `Cinode.from_env` is deleted; `_with_transport` stays.
- `cli/_output.py`: a module-level `client() -> Cinode` returns `Cinode()`,
  and `run()` calls it, which gives tests one seam to patch.
- `cli/config.py`:
  - a `config` typer group with an `@app.callback()` (it has one command
    for now, like `users profile`)
  - `cinode config show`
  - `ConfigReport(CinodeModel)`, with the fields of the design's table
- `show` resolves credentials with `Settings.resolve()`. A `CinodeError`
  goes to `fail()` (exit 3 for an `AuthError`). On success, `show` stats
  `credentials_path()` for `file_exists`, `file_mode` (`f"{stat.S_IMODE(mode):04o}"`)
  and `file_private` (`(mode & 0o077) == 0`), and writes the report with
  `write(..., raw=False, jsonl=False)`. It makes no request.
  `ConfigReport.source` is `Literal["env", "file"]`, while `Settings.source`
  also allows `"argument"`, which `resolve()` without arguments never returns; narrow it
  explicitly, as strict pyright requires.
- Registered in `cli/__init__.py` as `app.add_typer(config.app, name="config")`.
  `cinode schema` gains `config`.
- `tests/conftest.py`: an autouse fixture `_no_credentials_file` sets
  `CINODE_CREDENTIALS_FILE` to `tmp_path / "absent" / "credentials.toml"`.
  `tests/live/conftest.py` overrides it with a no-op fixture of the same name,
  so the live suite may use the developer's credentials file.
- `tests/cli/conftest.py`: the `cli_api` fixture patches
  `cinode.cli._output.client` (instead of `Cinode.from_env`) with a client
  built on `Settings.resolve()` and the no-sleep transport. Nothing else in
  that file changes.

Tests:
- [ ] **Review focus 1:** one parametrized test of `Settings.resolve` in
  `tests/test_config.py`, using an `env` mapping and a file under
  `tmp_path`. The cases:
  - both arguments, the pair in the environment, and a valid file:
    `source == "argument"`, with the arguments' credentials
  - `access_id` only: `ValueError`
  - `timeout=7` as an argument and `CINODE_TIMEOUT=5`: `timeout == 7`
  - the pair in the environment, and a valid file: `source == "env"`, with
    the environment's credentials
  - `CINODE_BASIC` in the environment, and a valid file: `source == "env"`
  - the pair in the environment, and a file that is not TOML: `source == "env"`,
    and no error
  - no credentials in the environment, a valid file and `CINODE_TIMEOUT=5`:
    `source == "file"`, `basic` encodes the file's credentials, `timeout == 5`
  - `CINODE_ACCESS_ID` only, and a valid file: `AuthError` naming
    `CINODE_ACCESS_SECRET`
  - nothing in the environment, and no file: an `AuthError` that begins "No
    Cinode credentials" and contains the path
- [ ] **Review focus 3:** one parametrized test of `read_credentials`. The cases:
  - a file that is not valid TOML, with the secret on the broken line
  - no `access_secret`
  - `access_id = 5`
  - `access_secret = ""`

  Each raises an `AuthError` whose message contains the path (and the key,
  where one is at fault) and does not contain `"s3cret-value"`.
- [ ] One parametrized test of `credentials_path`, with `HOME` set by
  `monkeypatch` and an explicit `env` mapping (the autouse fixture has put
  `CINODE_CREDENTIALS_FILE` in `os.environ`). The cases:
  - `CINODE_CREDENTIALS_FILE="~/c.toml"` gives `$HOME/c.toml`
  - an absolute `XDG_CONFIG_HOME` gives `$XDG_CONFIG_HOME/cinode/credentials.toml`
  - a relative `XDG_CONFIG_HOME` gives `$HOME/.config/cinode/credentials.toml`
- [ ] CLI, parametrized over the file modes `0o600` and `0o644`. The
  `cli_api` fixture's `CINODE_BASIC` is removed, and `CINODE_CREDENTIALS_FILE` points at
  a file under `tmp_path` holding `id-1.app.cinode.com` and `s3cret-value`:
  - `cinode users skills list me` succeeds, and the `/token` request carries
    `Basic base64("id-1.app.cinode.com:s3cret-value")`
  - `cinode config show` writes exactly `{"source": "file", "access_id":
    "id-1.app.cinode.com", "path": <path>, "file_exists": true, "file_mode":
    "0600" | "0644", "file_private": true | false}`, and `"s3cret-value"` is
    in neither stream
- [ ] **Review focus 2:** the existing CLI tests, including
  `test_no_credentials_is_an_auth_error`, and `tests/test_config.py`'s
  existing tests pass unedited.
- [ ] README:
  - *Credentials* gains the credentials file: its location, its two keys, that
    the environment wins, and `cinode config show`
  - the library quick start uses `Cinode()`, and no longer mentions
    `from_env`
  - the CLI list gains `cinode config show`
  - the "Version 0.1 covers …" paragraph gains a sentence about version 0.3

  CHANGELOG: an entry under *Unreleased*, with a *Breaking* line for the
  removal of `Cinode.from_env()` (use `Cinode()`).
- [ ] Run the four checks. Commit in two chunks: "Read credentials from a
  credentials file", "Add cinode config show".

### Task 2: `cinode init`

**Files:** `src/cinode/cli/config.py`, `src/cinode/cli/__init__.py`,
`src/cinode/cli/schema.py`, `tests/cli/conftest.py`, `tests/cli/test_cli.py`,
`tests/live/conftest.py`, `tests/live/test_acceptance.py`, `README.md`,
`CHANGELOG.md`.

**Consumes:** `credentials_path`, `decode_basic` and the resolving `Cinode(...)` from Task 1.

**Produces:**
- `cinode init [--access-id TEXT] [--from-env] [--force]`, registered at the
  root as `app.command("init")(config.init)`, and following the design's
  steps in order:
  1. If `credentials_path()` exists and `--force` is not given, `fail()` with a
     plain `CinodeError` naming the path and `--force` (exit 1), before any
     prompt or request.
  2. Take the credentials from `--from-env`, from the terminal, or from
     `--access-id` plus the first line of stdin, stripped. The terminal path
     is the one taken when `sys.stdin.isatty()`, and its prompts use
     `typer.prompt(..., err=True)`, with `hide_input=True` for the secret.
     Usage errors (exit 2) raise `typer.BadParameter` or `typer.UsageError`
     before any request:
     - `--from-env` with `--access-id`
     - `--from-env` with no usable credentials in the environment: none,
       half a pair, or a `CINODE_BASIC` that `decode_basic` cannot decode
     - no `--access-id` when stdin is not a terminal
     - an empty AccessId or secret
     - a value containing a control character (U+0000–U+001F or U+007F),
       or one that does not encode as UTF-8 (a lone surrogate from
       undecodable stdin)
  3. Verify: `with Cinode(access_id, secret) as c: who = c.whoami()`. The
     constructor applies `CINODE_BASE_URL` and `CINODE_TIMEOUT` itself. A
     `CinodeError` goes to `fail()`.
  4. Write with a private helper `_write_credentials(path, access_id, access_secret)`:
     - create the parent directory with `mkdir(mode=0o700, parents=True, exist_ok=True)`
     - build the text: the design's comment line, then each value quoted with
       `json.dumps(value, ensure_ascii=False)` (valid TOML once control
       characters are excluded)
     - check that `tomllib.loads` gives the values back
     - write it to a `tempfile.mkstemp(dir=path.parent)` file, then
       `os.replace` it onto `path`, and unlink the temporary file if
       anything fails
  5. Write `InitResult(CinodeModel)` (`path: str`, `access_id: str`,
     `company_id: int`, `user_id: int`, the ids from `who`) with `write()`.
- `cinode schema` gains `init`.
- `tests/cli/conftest.py`: the `cli` fixture gains a keyword-only
  `input: str | None = None`, passed to `runner.invoke`, so tests can feed
  stdin.
- `tests/live/conftest.py`: `cinode()` gains a keyword-only
  `env: Mapping[str, str] | None = None`, passed to `subprocess.run` as the
  whole environment.

Tests (under `tests/cli/test_cli.py`, with `CINODE_CREDENTIALS_FILE` set to
`tmp_path / "new" / "credentials.toml"`, whose directory does not exist
beforehand, except where a test creates it):
- [ ] **Review focus 4 and 6:** `cinode init --access-id id-1.app.cinode.com`
  with stdin `'s3cret-"\\:value\n'`:
  - it exits 0, and stdout is exactly `{"path": <path>, "access_id":
    "id-1.app.cinode.com", "company_id": 99, "user_id": 1001}`
  - the file has mode `0600`, and its new parent directory `0700`
  - `tomllib` reads the secret back unchanged
  - `/token` saw the matching Basic credential
  - the secret is in neither stream
  - the directory holds only `credentials.toml`
- [ ] **Review focus 5:** with `/token` returning 401, `init` exits 3 with an
  `AuthError` envelope, and `tmp_path / "new"` does not exist (or, if the
  implementation creates it before verifying, is empty).
- [ ] Parametrized over `--force`, with a file already at the path: without
  it, exit 1, the file unchanged and no request made; with it, exit 0 and the
  file replaced.
- [ ] **Review focus 6:** `init --from-env`, with only `CINODE_BASIC` set, to
  base64 of `id-2.app.cinode.com:pa:ss`, saves the AccessId
  `id-2.app.cinode.com` and the secret `pa:ss`.
- [ ] Parametrized usage errors, each exiting 2 with a `UsageError` envelope,
  no request and no file:
  - `--from-env --access-id x`
  - no `--access-id` (the runner's stdin is not a terminal)
  - empty stdin
- [ ] **Review focus 7:** the GET-only transport test passes unedited.
- [ ] Live: the `init` round trip. Skip it, with a message that names no
  data, when the environment holds neither the pair nor `CINODE_BASIC`.
  Otherwise, with `path = tmp_path / "credentials.toml"`:
  - `cinode init --from-env`, run with `os.environ` plus `CINODE_CREDENTIALS_FILE=path`,
    exits 0, and the file's mode is `0600`
  - `cinode whoami`, run with `os.environ` minus `CINODE_ACCESS_ID`,
    `CINODE_ACCESS_SECRET` and `CINODE_BASIC`, plus `CINODE_CREDENTIALS_FILE=path`,
    gives `.user_id` equal to the owner's
  - the file is deleted in a `finally` (or fixture teardown), whatever the
    outcome, since pytest keeps old `tmp_path` directories
- [ ] README: *Credentials* opens with `cinode init` (the terminal path, the
  stdin path for agents and scripts, and `--from-env` for migrating), and the
  environment variables become the alternative. The CLI list gains `cinode
  init`. CHANGELOG: the *Unreleased* entry covers it.
- [ ] Run the four checks, and `CINODE_LIVE_TESTS=1 uv run pytest -m live`
  (the slow tests included, since this is the last task). Commit in two
  chunks: "Add cinode init", "Test the init round trip live".

---

## Done when

- [ ] `uv run pytest`, `ruff check`, `ruff format --check` and `pyright` are
      clean, and the default test run takes under two seconds.
- [ ] `CINODE_LIVE_TESTS=1 uv run pytest -m live` passes against the owner's
      profile.
