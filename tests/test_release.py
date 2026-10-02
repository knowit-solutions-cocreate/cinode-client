from collections.abc import Callable
from pathlib import Path

import pytest
from release import (
    ReleaseError,
    archive_plan,
    check,
    date_changelog,
    mark_released,
    release_notes,
)

CHANGELOG = """\
# Changelog

## Unreleased

- **New:** a thing.

## 0.3.0 — 2026-09-24

Older.
"""


def test_the_release_notes_are_the_dated_section() -> None:
    dated = date_changelog(CHANGELOG, "0.4.0", "2026-10-02", "What the\n  release   does.")

    assert "## Unreleased\n\n## 0.4.0 — 2026-10-02\n\nWhat the release does.\n\n" in dated
    assert release_notes(dated, "0.4.0") == "What the release does.\n\n- **New:** a thing.\n"


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda: archive_plan("# Plan\n\n- [x] done\n- [ ] open\n", "0.4.0", "d"), "unticked"),
        (lambda: date_changelog("## Unreleased\n\n## 0.3.0\n", "0.4.0", "d", "s"), "empty"),
        (lambda: mark_released("| **v0.4** | Later | x |", "0.4.0", "d"), "in-progress"),
    ],
)
def test_prepare_refuses_a_version_that_is_not_done(
    edit: Callable[[], object], message: str
) -> None:
    with pytest.raises(ReleaseError, match=message):
        edit()


@pytest.mark.parametrize(
    ("version", "plan", "message"),
    [
        ("0.4.0", True, None),
        ("0.4.1", True, "version 0.4.0"),
        ("0.4.0", False, "v0.4.md"),
        ("0.4.0-rc1", True, "not a version"),
    ],
)
def test_check_matches_the_tag_to_the_repository(
    tmp_path: Path, version: str, plan: bool, message: str | None
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.4.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("## 0.4.0 — 2026-10-02\n\nNotes.\n")
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    if plan:
        (tmp_path / "docs" / "plans" / "v0.4.md").write_text("# Plan\n")

    if message is None:
        check(tmp_path, version)
    else:
        with pytest.raises(ReleaseError, match=message):
            check(tmp_path, version)
