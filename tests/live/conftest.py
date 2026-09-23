"""Fixtures for the live acceptance suite: the owner's ids, the `cinode` binary and `jq`.

Each `cinode` process fetches its own token, and `/token` allows two per two
seconds per AccessId, so `cinode()` leaves over a second between runs.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

type Cinode = Callable[..., subprocess.CompletedProcess[str]]
type Jq = Callable[..., bool]

MIN_INTERVAL = 1.1  # seconds between `cinode` processes


@dataclass(frozen=True)
class Owner:
    """The account owner's profile facts the suite asserts on."""

    user_id: int
    team_id: int
    keyword_id: int
    keyword_name: str
    synonym_id: int
    unreadable_user_id: int


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@pytest.fixture(scope="session", autouse=True)
def _require_jq() -> None:  # pyright: ignore[reportUnusedFunction]
    if shutil.which("jq") is None:
        pytest.skip("jq is not on PATH")


@pytest.fixture(scope="session")
def owner() -> Owner:
    return Owner(
        user_id=_env_int("CINODE_TEST_USER_ID", 158773),
        team_id=_env_int("CINODE_TEST_TEAM_ID", 9873),
        keyword_id=_env_int("CINODE_TEST_KEYWORD_ID", 22070),
        keyword_name=os.environ.get("CINODE_TEST_KEYWORD_NAME", "Python"),
        synonym_id=_env_int("CINODE_TEST_SYNONYM_ID", 2930),
        unreadable_user_id=_env_int("CINODE_TEST_UNREADABLE_USER_ID", 1),
    )


def _binary() -> str:
    found = shutil.which("cinode")
    if found is not None:
        return found
    return str(Path(sys.executable).with_name("cinode"))


@pytest.fixture(scope="session")
def cinode() -> Cinode:
    """Run the installed `cinode` with `args`, capturing text output, paced for `/token`."""
    binary = _binary()
    last = 0.0

    def run(*args: str | int) -> subprocess.CompletedProcess[str]:
        nonlocal last
        wait = last + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return subprocess.run(
                [binary, *map(str, args)],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        finally:
            last = time.monotonic()

    return run


@pytest.fixture(scope="session")
def jq() -> Jq:
    """`jq -e expr` on `document`, with each keyword argument bound by `--argjson`."""

    def run(expr: str, document: str, **argjson: Any) -> bool:
        args: list[str] = []
        for name, value in argjson.items():
            args += ["--argjson", name, json.dumps(value)]
        result = subprocess.run(
            ["jq", "-e", *args, expr],
            input=document,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0

    return run
