"""`cinode schema`: the JSON Schema of each output model."""

import json
import sys
from typing import Annotated

import typer

from cinode.models import (
    CinodeModel,
    Keyword,
    Profile,
    Resume,
    ResumeSummary,
    Skill,
    Team,
    TeamMember,
    User,
    UserSummary,
    WhoAmI,
)
from cinode.ops import TeamSkills

MODELS: dict[str, type[CinodeModel]] = {
    "keyword": Keyword,
    "profile": Profile,
    "resume": Resume,
    "resume-summary": ResumeSummary,
    "skill": Skill,
    "team": Team,
    "team-member": TeamMember,
    "team-skills": TeamSkills,
    "user": User,
    "user-summary": UserSummary,
    "whoami": WhoAmI,
}

ModelArg = Annotated[str | None, typer.Argument(help="A model name. Omit it to list the names.")]


def schema(model: ModelArg = None) -> None:
    """The JSON Schema of an output model, or the sorted model names."""
    if model is None:
        document: object = sorted(MODELS)
    elif model in MODELS:
        document = MODELS[model].model_json_schema(mode="serialization")
    else:
        names = ", ".join(sorted(MODELS))
        raise typer.BadParameter(f"unknown model {model!r}; valid names: {names}.")
    sys.stdout.write(json.dumps(document, ensure_ascii=False) + "\n")
