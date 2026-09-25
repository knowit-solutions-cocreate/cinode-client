"""`--format table`: column paths, default columns, and rendering with `rich`.

A table's layout is not part of the output contract; its column paths are.
"""

import re
import types
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Union, cast, get_args, get_origin

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from cinode.models import (
    CinodeModel,
    Keyword,
    ResumeSummary,
    Skill,
    Team,
    TeamMember,
    UserSummary,
)
from cinode.ops import TeamSkills


@dataclass(frozen=True)
class Column:
    """A column of a table: a path into the row model, and its header."""

    path: str
    label: str


class MemberSkillRow(CinodeModel):
    """One row of `teams skills` as a table: a member, and one of their skills or none."""

    user: UserSummary
    skill: Skill | None = None


def _model_of(annotation: Any) -> type[CinodeModel] | None:
    """The `CinodeModel` subclass `annotation` names, once `None` is taken out, if any."""
    if get_origin(annotation) in (Union, types.UnionType):
        rest = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(rest) != 1:
            return None
        annotation = rest[0]
    if isinstance(annotation, type) and issubclass(annotation, CinodeModel):
        return annotation
    return None


def _is_container(annotation: Any) -> bool:
    """Whether `annotation`, once `None` is taken out, is a list or dict: not a column."""
    candidates = get_args(annotation) if get_origin(annotation) in (Union, types.UnionType) else ()
    for candidate in candidates or (annotation,):
        if candidate is type(None):
            continue
        origin = get_origin(candidate) or candidate
        if isinstance(origin, type) and issubclass(origin, (list, dict, tuple, set, frozenset)):
            return True
    return False


def column_paths(model: type[CinodeModel]) -> list[str]:
    """Every column path of `model`, in field order: declared fields, then computed ones.

    A path goes through nested models, optional ones included, stops at lists
    and dicts, which are not columns, and ends at anything else.
    """
    annotations: list[tuple[str, Any]] = [
        (name, field.annotation) for name, field in model.model_fields.items()
    ]
    annotations += [
        (name, field.return_type) for name, field in model.model_computed_fields.items()
    ]
    paths: list[str] = []
    for name, annotation in annotations:
        nested = _model_of(annotation)
        if nested is not None:
            paths += [f"{name}.{path}" for path in column_paths(nested)]
        elif not _is_container(annotation):
            paths.append(name)
    return paths


def humanise(path: str) -> str:
    """`path` as a header: dots and underscores become spaces, the first letter a capital."""
    text = path.replace(".", " ").replace("_", " ")
    return text[:1].upper() + text[1:]


def _columns(*pairs: tuple[str, str]) -> tuple[Column, ...]:
    return tuple(Column(path, label) for path, label in pairs)


DEFAULT_COLUMNS: dict[type[CinodeModel], tuple[Column, ...]] = {
    UserSummary: _columns(("id", "Id"), ("full_name", "Name")),
    Skill: _columns(
        ("keyword_id", "Keyword id"),
        ("name", "Name"),
        ("level", "Level"),
        ("level_goal", "Goal"),
        ("years_experience", "Years"),
        ("favourite", "Favourite"),
    ),
    Team: _columns(("id", "Id"), ("name", "Name"), ("parent_team_id", "Parent")),
    TeamMember: _columns(
        ("user_id", "User id"),
        ("user.full_name", "Name"),
        ("availability_percent", "Availability %"),
    ),
    ResumeSummary: _columns(
        ("id", "Id"), ("title", "Title"), ("language", "Language"), ("updated", "Updated")
    ),
    Keyword: _columns(("id", "Id"), ("name", "Name"), ("type", "Type"), ("verified", "Verified")),
    MemberSkillRow: _columns(
        ("user.id", "User id"),
        ("user.full_name", "Name"),
        ("skill.keyword_id", "Keyword id"),
        ("skill.name", "Skill"),
        ("skill.level", "Level"),
        ("skill.years_experience", "Years"),
    ),
}


def parse_columns(value: str, model: type[CinodeModel]) -> tuple[Column, ...]:
    """The columns `--columns` names, in its order, each with its header.

    A path keeps its label from `DEFAULT_COLUMNS[model]` if it is one of the
    defaults, and is otherwise humanised. Raises `typer.BadParameter` (exit 2)
    for an empty value, an empty item, or a path `model` does not have; the
    last lists the valid paths.
    """
    paths = [item.strip() for item in value.split(",")]
    if not any(paths):
        raise typer.BadParameter("must name at least one column path.", param_hint="'--columns'")
    if not all(paths):
        raise typer.BadParameter(f"has an empty item: {value!r}.", param_hint="'--columns'")
    valid = column_paths(model)
    unknown = [path for path in paths if path not in valid]
    if unknown:
        noun = "path" if len(unknown) == 1 else "paths"
        raise typer.BadParameter(
            f"unknown column {noun} {', '.join(map(repr, unknown))}. "
            f"Valid paths: {', '.join(valid)}.",
            param_hint="'--columns'",
        )
    labels = {column.path: column.label for column in DEFAULT_COLUMNS.get(model, ())}
    return tuple(Column(path, labels.get(path, humanise(path))) for path in paths)


def member_skill_rows(result: TeamSkills) -> list[MemberSkillRow]:
    """One row per member and skill, in member order, then Cinode's skill order.

    A member with no skills has one row, with `skill=None`.
    """
    rows: list[MemberSkillRow] = []
    for member in result.members:
        if not member.skills:
            rows.append(MemberSkillRow(user=member.user))
        rows += [MemberSkillRow(user=member.user, skill=skill) for skill in member.skills]
    return rows


_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")


def _printable(text: str) -> str:
    """`text` with every C0 and C1 control character but `\\n` replaced by U+FFFD.

    Cinode's text must not reach the terminal as an escape sequence. A newline
    is kept: `rich` breaks the line there, as it does when a cell folds.
    """
    return _CONTROL.sub("\ufffd", text)


def _cell(data: Any, path: str) -> str:
    value = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return ""
        value = cast("dict[str, Any]", value).get(part)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return _printable(str(value))


def cells(item: CinodeModel, columns: Sequence[Column]) -> list[str]:
    """One string per column: the value at its path in `item.model_dump(mode="json")`.

    `null`, or a `null` model on the way, is an empty cell; a boolean is `true`
    or `false`; anything else is its string, with control characters replaced.
    """
    data = item.model_dump(mode="json")
    return [_cell(data, column.path) for column in columns]


def _heading(text: str | None) -> Text | None:
    return None if text is None else Text(_printable(text), no_wrap=True, overflow="ignore")


def render(
    result: CinodeModel | Sequence[CinodeModel],
    *,
    model: type[CinodeModel],
    columns: tuple[Column, ...] | None = None,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """Print `result` to stdout as a table whose rows are `model`s.

    A list is one row per element, with `DEFAULT_COLUMNS[model]` unless
    `columns` is given. A single object is a *Field* and *Value* table, one row
    per path. Cinode's text is printed as it is: markup, emoji codes and
    highlighting are off, and control characters are replaced. The title and
    caption are never cropped.
    """
    table = Table(title=_heading(title), caption=_heading(caption))
    if isinstance(result, CinodeModel):
        rows = columns or tuple(Column(p, humanise(p)) for p in column_paths(model))
        table.add_column("Field", overflow="fold")
        table.add_column("Value", overflow="fold")
        for column, value in zip(rows, cells(result, rows), strict=True):
            table.add_row(Text(humanise(column.path)), Text(value))
    else:
        shown = columns or DEFAULT_COLUMNS[model]
        for column in shown:
            table.add_column(column.label, overflow="fold")
        for item in result:
            table.add_row(*(Text(value) for value in cells(item, shown)))
    Console(highlight=False, markup=False, emoji=False).print(table, crop=False)
