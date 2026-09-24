import base64
from pathlib import Path

import pytest

from cinode._config import Settings, credentials_path, read_credentials
from cinode.errors import AuthError

SECRET = "s3cret-value"
FILE_ID = "id-1.app.cinode.com"
VALID_FILE = f'access_id = "{FILE_ID}"\naccess_secret = "{SECRET}"\n'
PAIR = {"CINODE_ACCESS_ID": "id-env.app.cinode.com", "CINODE_ACCESS_SECRET": "env-secret"}


def _basic(access_id: str, access_secret: str) -> str:
    return base64.b64encode(f"{access_id}:{access_secret}".encode()).decode()


def test_id_and_secret_win_over_basic() -> None:
    settings = Settings.from_env(
        {"CINODE_ACCESS_ID": "id", "CINODE_ACCESS_SECRET": "secret", "CINODE_BASIC": "b3RoZXI="}
    )
    assert settings.basic == base64.b64encode(b"id:secret").decode()


@pytest.mark.parametrize(
    ("env", "match"),
    [
        ({}, "No Cinode credentials"),
        # Half a pair must not fall back to CINODE_BASIC, which may be another account.
        ({"CINODE_ACCESS_ID": "id", "CINODE_BASIC": "b3RoZXI="}, "CINODE_ACCESS_SECRET"),
    ],
)
def test_missing_credentials_is_an_auth_error(env: dict[str, str], match: str) -> None:
    with pytest.raises(AuthError, match=match):
        Settings.from_env(env)


def test_whitespace_is_stripped_from_basic() -> None:
    assert Settings.from_env({"CINODE_BASIC": "YWJj\nZGVm \n"}).basic == "YWJjZGVm"


@pytest.mark.parametrize(
    ("args", "env", "file", "expected"),
    [
        pytest.param(
            {"access_id": "id-arg.app.cinode.com", "access_secret": "arg-secret"},
            PAIR,
            VALID_FILE,
            {"source": "argument", "basic": _basic("id-arg.app.cinode.com", "arg-secret")},
            id="arguments-win",
        ),
        pytest.param({"access_id": "id-arg.app.cinode.com"}, {}, None, ValueError, id="half-args"),
        pytest.param(
            {"timeout": 7}, PAIR | {"CINODE_TIMEOUT": "5"}, None, {"timeout": 7}, id="timeout-arg"
        ),
        pytest.param(
            {},
            PAIR,
            VALID_FILE,
            {"source": "env", "basic": _basic("id-env.app.cinode.com", "env-secret")},
            id="env-wins",
        ),
        pytest.param(
            {}, {"CINODE_BASIC": _basic("id-b", "b")}, VALID_FILE, {"source": "env"}, id="basic"
        ),
        # The environment wins as a whole: a broken file is never opened.
        pytest.param(
            {}, PAIR, f'access_secret = "{SECRET}\n', {"source": "env"}, id="env-broken-file"
        ),
        pytest.param(
            {},
            {"CINODE_TIMEOUT": "5"},
            VALID_FILE,
            {"source": "file", "basic": _basic(FILE_ID, SECRET), "timeout": 5},
            id="file",
        ),
        # Half a pair never falls back to the file, which may be another account.
        pytest.param(
            {},
            {"CINODE_ACCESS_ID": "id-env.app.cinode.com"},
            VALID_FILE,
            "CINODE_ACCESS_SECRET",
            id="half-env",
        ),
        pytest.param({}, {}, None, "No Cinode credentials", id="nothing"),
    ],
)
def test_resolve_takes_arguments_then_env_then_file(
    tmp_path: Path,
    args: dict[str, object],
    env: dict[str, str],
    file: str | None,
    expected: dict[str, object] | type[Exception] | str,
) -> None:
    path = tmp_path / "credentials.toml"
    if file is not None:
        path.write_text(file)

    def resolve() -> Settings:
        return Settings.resolve(**args, env=env, credentials_file=path)  # pyright: ignore[reportArgumentType]

    if isinstance(expected, type):
        with pytest.raises(expected):
            resolve()
    elif isinstance(expected, str):
        with pytest.raises(AuthError) as info:
            resolve()
        assert info.value.message.startswith(expected)
        if expected.startswith("No Cinode"):
            assert str(path) in info.value.message
    else:
        settings = resolve()
        for name, value in expected.items():
            assert getattr(settings, name) == value


@pytest.mark.parametrize(
    ("text", "key"),
    [
        (f'access_id = "{FILE_ID}"\naccess_secret = "{SECRET}\n', None),
        (f'access_id = "{FILE_ID}"\n', "access_secret"),
        (f'access_id = 5\naccess_secret = "{SECRET}"\n', "access_id"),
        (f'access_id = "{FILE_ID}"\naccess_secret = ""\n', "access_secret"),
    ],
    ids=["not-toml", "no-secret", "id-not-a-string", "empty-secret"],
)
def test_a_malformed_file_names_the_path_and_key_but_no_value(
    tmp_path: Path, text: str, key: str | None
) -> None:
    path = tmp_path / "credentials.toml"
    path.write_text(text)
    with pytest.raises(AuthError) as info:
        read_credentials(path)
    message = info.value.message
    assert str(path) in message
    assert key is None or key in message
    assert SECRET not in message


@pytest.mark.parametrize(
    ("env", "relative"),
    [
        ({"CINODE_CREDENTIALS_FILE": "~/c.toml"}, "c.toml"),
        ({"XDG_CONFIG_HOME": "{home}/xdg"}, "xdg/cinode/credentials.toml"),
        ({"XDG_CONFIG_HOME": "xdg"}, ".config/cinode/credentials.toml"),
    ],
    ids=["explicit", "xdg-absolute", "xdg-relative"],
)
def test_credentials_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str], relative: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env = {name: value.format(home=tmp_path) for name, value in env.items()}
    assert credentials_path(env) == tmp_path / relative
