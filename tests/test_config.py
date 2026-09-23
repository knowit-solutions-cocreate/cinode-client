import base64

import pytest

from cinode._config import Settings
from cinode.errors import AuthError


def test_id_and_secret_win_over_basic() -> None:
    settings = Settings.from_env(
        {"CINODE_ACCESS_ID": "id", "CINODE_ACCESS_SECRET": "secret", "CINODE_BASIC": "b3RoZXI="}
    )
    assert settings.basic == base64.b64encode(b"id:secret").decode()


def test_no_credentials_is_an_auth_error() -> None:
    with pytest.raises(AuthError):
        Settings.from_env({})


def test_whitespace_is_stripped_from_basic() -> None:
    assert Settings.from_env({"CINODE_BASIC": "YWJj\nZGVm \n"}).basic == "YWJjZGVm"
