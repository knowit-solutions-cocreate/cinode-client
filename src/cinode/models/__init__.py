"""The models the library returns. Field names are ours, not Cinode's."""

from cinode.models._base import CinodeModel
from cinode.models.skills import Keyword, Skill

__all__ = ["CinodeModel", "Keyword", "Skill"]
