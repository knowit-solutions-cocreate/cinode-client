"""Keywords: the skill names that skills refer to."""

from urllib.parse import quote

from cinode.models import Keyword
from cinode.resources._base import Resource


class Keywords(Resource):
    """`keywords`: the company's keyword catalogue."""

    def search(self, term: str) -> list[Keyword]:
        """The keywords matching `term`.

        The term is stripped and sent as one percent-encoded path segment, so
        `CI/CD` or `C#` cannot change the path. Raises `ValueError` if it is empty.
        """
        stripped = term.strip()
        if not stripped:
            raise ValueError("term must not be empty.")
        return self._list(Keyword, f"keywords/search/{quote(stripped, safe='')}")
