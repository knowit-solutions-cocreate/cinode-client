"""Parity: `cinode teams skills` reads the same data as the reference script.

Both outputs are projected through `jq` to sorted `{user_id, skills: [{keyword_id,
level}]}` and compared. Ours maps an unrated `null` level to 0, which is what
the script passes through. Neither output is written to disk or shown: a
failure reports only which side failed, or that the projections differ.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from live.conftest import Cinode, Owner

REFERENCE_SCRIPT = Path(
    os.environ.get("CINODE_REFERENCE_SCRIPT", "~/code/sandbox/cinode-helper/fetch-team-skills.py")
).expanduser()

OURS = (
    "[.members[] | {user_id: .user.id, skills: ([.skills[] | "
    "{keyword_id, level: (.level // 0)}] | sort_by(.keyword_id))}] | sort_by(.user_id)"
)
THEIRS = (
    "[.[] | {user_id: .id, skills: ([.skills[] | "
    "{keyword_id: .id, level}] | sort_by(.keyword_id))}] | sort_by(.user_id)"
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("CINODE_LIVE_TESTS") != "1", reason="set CINODE_LIVE_TESTS=1"
    ),
    pytest.mark.skipif(
        not REFERENCE_SCRIPT.is_file(), reason="the reference script is not present"
    ),
    pytest.mark.skipif(not os.environ.get("CINODE_BASIC"), reason="CINODE_BASIC is not set"),
]


def project(expr: str, document: str) -> str | None:
    """`jq -cS expr` on `document`, or None when jq fails."""
    result = subprocess.run(
        ["jq", "-cS", expr],
        input=document,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def test_parity(cinode: Cinode, owner: Owner) -> None:
    ours = cinode("teams", "skills", owner.team_id)
    code = ours.returncode
    assert code == 0, ours.stderr  # stderr holds only the error envelope

    time.sleep(1.1)  # the script fetches its own token; /token allows 2 per 2 s
    theirs = subprocess.run(
        [sys.executable, str(REFERENCE_SCRIPT), str(owner.team_id)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    code = theirs.returncode
    assert code == 0, "the reference script failed"  # its stderr names members

    left = project(OURS, ours.stdout)
    right = project(THEIRS, theirs.stdout)
    projected = left is not None and right is not None
    assert projected, "jq could not project one of the outputs"
    same = left == right
    assert same, "cinode and the reference script disagree"
