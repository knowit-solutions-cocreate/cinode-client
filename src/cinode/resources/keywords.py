"""Keywords: the skill names that skills refer to."""

from urllib.parse import quote

from cinode.models import Keyword
from cinode.resources._base import Resource


class Keywords(Resource):
    """`keywords`: the company's keyword catalogue."""

    def search(self, term: str) -> list[Keyword]:
        """The keywords matching `term`.

        The term is stripped and sent as one percent-encoded path segment, so
        `CI/CD` or `C#` cannot change the path. Raises `ValueError` if it is not
        a string, is empty, or is made only of dots (`.` and `..` would be
        collapsed as dot segments and reach a different endpoint).
        """
        if not isinstance(term, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"term must be a str, not {term!r}.")
        stripped = term.strip()
        if not stripped:
            raise ValueError("term must not be empty.")
        if not stripped.strip("."):
            raise ValueError("term must not be made only of dots.")
        return self._list(Keyword, f"keywords/search/{quote(stripped, safe='')}")
