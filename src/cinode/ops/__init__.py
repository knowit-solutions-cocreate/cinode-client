"""Operations that combine several calls. Resources stay one-to-one with endpoints."""

from cinode.ops._members import Skipped
from cinode.ops.team_profiles import MemberProfile, TeamProfiles, team_profiles
from cinode.ops.team_skills import MemberSkills, TeamSkills, team_skills

__all__ = [
    "MemberProfile",
    "MemberSkills",
    "Skipped",
    "TeamProfiles",
    "TeamSkills",
    "team_profiles",
    "team_skills",
]
