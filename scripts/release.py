"""Release helper: prepares the release PR, and checks and describes a tag.

    uv run scripts/release.py prepare 0.4.0 --summary "One paragraph."
    uv run scripts/release.py check 0.4.0
    uv run scripts/release.py notes 0.4.0

`prepare` makes the release PR's edits in the working tree; it commits nothing.
`check` and `notes` are what the release workflow runs on a pushed tag.
"""

import argparse
import datetime
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

REPO_URL = "https://github.com/knowit-solutions-cocreate/cinode-client"
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class ReleaseError(Exception):
    """The repository is not in the state a release needs."""


def minor(version: str) -> str:
    """`0.4.0` → `v0.4`, the name of a version's plan and roadmap row."""
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise ReleaseError(f"not a version: {version!r}, expected MAJOR.MINOR.PATCH")
    return f"v{match[1]}.{match[2]}"


def release_url(version: str) -> str:
    return f"{REPO_URL}/releases/tag/v{version}"


def archive_plan(plan: str, version: str, date: str) -> str:
    """The plan with the archive banner after its title. It refuses open tasks."""
    if "- [ ]" in plan:
        raise ReleaseError("docs/plan.md still has unticked boxes")
    title, sep, rest = plan.partition("\n\n")
    if not title.startswith("# ") or not sep:
        raise ReleaseError("docs/plan.md does not start with a title")
    banner = (
        "> **Archived.** This plan was carried out in full and released as\n"
        f"> [v{version}]({release_url(version)})\n"
        f"> on {date}. It is frozen: task numbers here are what the PR titles and\n"
        "> review comments refer to. The current state lives in\n"
        "> [`docs/design.md`](../design.md); what comes next is in\n"
        "> [`docs/roadmap.md`](../roadmap.md)."
    )
    return f"{title}\n\n{banner}\n\n{rest}"


def plan_stub(version: str) -> str:
    name = minor(version)
    return (
        "# cinode-client — current plan\n"
        "\n"
        f"No version is in progress. {name} is released; its plan is archived at\n"
        f"[`docs/plans/{name}.md`](plans/{name}.md).\n"
        "\n"
        "The next version is listed in [`docs/roadmap.md`](roadmap.md). When work on it\n"
        "starts, its plan replaces this file, and at its release it moves to\n"
        "`docs/plans/v<major>.<minor>.md`.\n"
    )


def date_changelog(changelog: str, version: str, date: str, summary: str) -> str:
    """Turns the *Unreleased* entries into `version`'s section, under `summary`."""
    heading = "## Unreleased\n\n"
    if heading not in changelog:
        raise ReleaseError("CHANGELOG.md has no '## Unreleased' section")
    head, _, rest = changelog.partition(heading)
    if rest.startswith("## ") or not rest.strip():
        raise ReleaseError("CHANGELOG.md's Unreleased section is empty")
    intro = textwrap.fill(" ".join(summary.split()), width=78)
    return f"{head}{heading}## {version} — {date}\n\n{intro}\n\n{rest}"


def mark_released(roadmap: str, version: str, date: str) -> str:
    """Marks `version`'s roadmap row released, with links to its plan and release."""
    name = minor(version)
    in_progress = f"| **{name}** | In progress ([plan](plan.md)) |"
    if in_progress not in roadmap:
        raise ReleaseError(f"docs/roadmap.md has no in-progress row for {name}")
    released = (
        f"| **{name}** | Released {date} ([plan](plans/{name}.md), "
        f"[release]({release_url(version)})) |"
    )
    return roadmap.replace(in_progress, released)


def set_version(pyproject: str, version: str) -> str:
    new, count = re.subn(
        r'^version = "[^"]*"$', f'version = "{version}"', pyproject, count=1, flags=re.M
    )
    if count != 1:
        raise ReleaseError("pyproject.toml has no version line")
    return new


def release_notes(changelog: str, version: str) -> str:
    """`version`'s changelog section, without its heading: the release's body."""
    match = re.search(
        rf"^## {re.escape(version)} — \d{{4}}-\d{{2}}-\d{{2}}\n(.*?)(?=^## |\Z)",
        changelog,
        flags=re.M | re.S,
    )
    if match is None:
        raise ReleaseError(f"CHANGELOG.md has no dated section for {version}")
    return match[1].strip() + "\n"


def check(root: Path, version: str) -> None:
    """Everything a tag `v<version>` needs to be released."""
    plan = root / "docs" / "plans" / f"{minor(version)}.md"
    found = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    if found != version:
        raise ReleaseError(f"pyproject.toml has version {found}, not {version}")
    release_notes((root / "CHANGELOG.md").read_text(), version)
    if not plan.is_file():
        raise ReleaseError(f"{plan.relative_to(root)} is missing")


def prepare(root: Path, version: str, date: str, summary: str) -> None:
    plan_path = root / "docs" / "plan.md"
    archived = root / "docs" / "plans" / f"{minor(version)}.md"
    if archived.exists():
        raise ReleaseError(f"{archived.relative_to(root)} already exists")
    # Every edit is computed before any file changes, so a refusal changes nothing.
    plan = archive_plan(plan_path.read_text(), version, date)
    changelog = date_changelog((root / "CHANGELOG.md").read_text(), version, date, summary)
    roadmap = mark_released((root / "docs" / "roadmap.md").read_text(), version, date)
    pyproject = set_version((root / "pyproject.toml").read_text(), version)

    subprocess.run(["git", "mv", str(plan_path), str(archived)], cwd=root, check=True)
    archived.write_text(plan)
    plan_path.write_text(plan_stub(version))
    (root / "CHANGELOG.md").write_text(changelog)
    (root / "docs" / "roadmap.md").write_text(roadmap)
    (root / "pyproject.toml").write_text(pyproject)
    subprocess.run(["uv", "lock"], cwd=root, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release helper for cinode-client.")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="make the release PR's edits")
    prep.add_argument("version")
    prep.add_argument("--summary", required=True, help="the changelog section's intro")
    prep.add_argument("--date", default=datetime.date.today().isoformat())
    commands.add_parser("check", help="check that a tag can be released").add_argument("version")
    commands.add_parser("notes", help="print the release notes").add_argument("version")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    try:
        match args.command:
            case "prepare":
                prepare(root, args.version, args.date, args.summary)
            case "check":
                check(root, args.version)
            case _:
                sys.stdout.write(release_notes((root / "CHANGELOG.md").read_text(), args.version))
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
