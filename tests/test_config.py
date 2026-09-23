import base64

import pytest

from cinode._config import Settings
from cinode.errors import AuthError


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
