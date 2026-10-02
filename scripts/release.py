"""Release helper: prepares the release PR, and checks and describes a tag.

    uv run scripts/release.py prepare --summary "One paragraph."
    uv run scripts/release.py tag
    uv run scripts/release.py check 0.4.0
    uv run scripts/release.py notes 0.4.0

`prepare` releases the roadmap's in-progress version, and `tag` the version
`origin/main` has; either takes a version, which must then agree.

`prepare` makes the release PR's edits in the working tree; it commits nothing.
`tag` checks `origin/main`, then tags it and pushes the tag, which publishes.
`check` and `notes` are what the release workflow runs on a pushed tag.
"""

import argparse
import datetime
import posixpath
import re
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import Callable
from pathlib import Path

REPO_URL = "https://github.com/knowit-solutions-cocreate/cinode-client"
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
# A Markdown link to a relative path: no scheme, not an anchor, not absolute.
RELATIVE_LINK_RE = re.compile(r"\]\((?![a-z]+:|#|/)([^)\s]+)\)")


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
    """The plan as `docs/plans/` holds it: the archive banner after its title, and
    its relative links rewritten to work from there. It refuses open tasks."""
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
    rest = RELATIVE_LINK_RE.sub(
        lambda link: f"]({posixpath.normpath(posixpath.join('..', link[1]))})", rest
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


def in_progress(roadmap: str) -> str:
    """The version the roadmap has in progress, `v0.4` → `0.4.0`."""
    found = re.findall(r"^\| \*\*v(\d+\.\d+)\*\* \| In progress ", roadmap, flags=re.M)
    if len(found) != 1:
        raise ReleaseError("docs/roadmap.md does not have exactly one version in progress")
    return f"{found[0]}.0"


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


def project_version(pyproject: str | None) -> str:
    try:
        return tomllib.loads(pyproject or "")["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError) as error:
        raise ReleaseError("pyproject.toml has no [project] version") from error


def set_version(pyproject: str, version: str) -> str:
    new, count = re.subn(
        r'^version = "[^"]*"$', f'version = "{version}"', pyproject, count=1, flags=re.M
    )
    if count != 1 or project_version(new) != version:
        raise ReleaseError("pyproject.toml has no [project] version line first")
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


def release_body(changelog: str, version: str) -> str:
    """The release's body: `version`'s changelog section, then how to install it."""
    wheel = f"{REPO_URL}/releases/download/v{version}/cinode_client-{version}-py3-none-any.whl"
    return (
        f"{release_notes(changelog, version)}\n"
        "### Install\n\n"
        f"```sh\nuv tool install {wheel}\n```\n\n"
        "See the README for credentials, the CLI output contract and exit codes.\n"
    )


Reader = Callable[[str], str | None]
"""Reads a file by its path in the repository, or gives None if it is missing."""


def read_tree(root: Path) -> Reader:
    def read(path: str) -> str | None:
        file = root / path
        return file.read_text() if file.is_file() else None

    return read


def read_commit(root: Path, commit: str) -> Reader:
    def read(path: str) -> str | None:
        shown = subprocess.run(
            ["git", "show", f"{commit}:{path}"], cwd=root, capture_output=True, text=True
        )
        return shown.stdout if shown.returncode == 0 else None

    return read


def check(read: Reader, version: str) -> None:
    """Everything a tag `v<version>` needs to be released."""
    plan = f"docs/plans/{minor(version)}.md"
    found = project_version(read("pyproject.toml"))
    if found != version:
        raise ReleaseError(f"pyproject.toml has version {found}, not {version}")
    release_notes(read("CHANGELOG.md") or "", version)
    if read(plan) is None:
        raise ReleaseError(f"{plan} is missing")


def agree(found: str, given: str | None) -> str:
    if given is not None and given != found:
        raise ReleaseError(f"the version is {found}, not {given}")
    return found


def tag(root: Path, version: str | None) -> None:
    """Tags `origin/main` with its version and pushes the tag, once `check` passes there."""
    subprocess.run(["git", "fetch", "--quiet", "--tags", "origin", "main"], cwd=root, check=True)
    read = read_commit(root, "origin/main")
    version = agree(project_version(read("pyproject.toml")), version)
    check(read, version)
    name = f"v{version}"
    exists = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{name}"],
        cwd=root,
        capture_output=True,
    )
    if exists.returncode == 0:
        raise ReleaseError(f"the tag {name} already exists")
    message = f"cinode-client {version}"
    subprocess.run(["git", "tag", "-a", name, "-m", message, "origin/main"], cwd=root, check=True)
    subprocess.run(["git", "push", "origin", name], cwd=root, check=True)
    print(f"Pushed {name}; the release workflow publishes it: {REPO_URL}/actions")


def prepare(root: Path, version: str | None, date: str, summary: str) -> None:
    roadmap = (root / "docs" / "roadmap.md").read_text()
    version = agree(in_progress(roadmap), version)
    plan_path = root / "docs" / "plan.md"
    archived = root / "docs" / "plans" / f"{minor(version)}.md"
    if archived.exists():
        raise ReleaseError(f"{archived.relative_to(root)} already exists")
    # Every edit is computed before any file changes, so a refusal changes nothing.
    plan = archive_plan(plan_path.read_text(), version, date)
    changelog = date_changelog((root / "CHANGELOG.md").read_text(), version, date, summary)
    roadmap = mark_released(roadmap, version, date)
    pyproject = set_version((root / "pyproject.toml").read_text(), version)

    # `uv lock` is the step most likely to fail, so it goes first.
    (root / "pyproject.toml").write_text(pyproject)
    subprocess.run(["uv", "lock"], cwd=root, check=True)
    subprocess.run(["git", "mv", str(plan_path), str(archived)], cwd=root, check=True)
    archived.write_text(plan)
    plan_path.write_text(plan_stub(version))
    (root / "CHANGELOG.md").write_text(changelog)
    (root / "docs" / "roadmap.md").write_text(roadmap)
    check(read_tree(root), version)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release helper for cinode-client.")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="make the release PR's edits")
    prep.add_argument("version", nargs="?", help="default: the roadmap's in-progress one")
    prep.add_argument("--summary", required=True, help="the changelog section's intro")
    prep.add_argument("--date", default=datetime.date.today().isoformat())
    commands.add_parser("check", help="check that a tag can be released").add_argument("version")
    commands.add_parser("notes", help="print the release's body").add_argument("version")
    tag_ = commands.add_parser("tag", help="tag origin/main and push the tag")
    tag_.add_argument("version", nargs="?", help="default: the one origin/main has")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    try:
        match args.command:
            case "prepare":
                prepare(root, args.version, args.date, args.summary)
            case "check":
                check(read_tree(root), args.version)
            case "tag":
                tag(root, args.version)
            case _:
                sys.stdout.write(release_body((root / "CHANGELOG.md").read_text(), args.version))
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
