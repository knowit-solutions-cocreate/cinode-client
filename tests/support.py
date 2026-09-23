"""Shared test helpers. Tests import from here; pytest puts `tests/` on the path."""

import base64
import json

BASE_URL = "https://api.test"
USER_ID = 1001
COMPANY_ID = 99
TEAM_ID = 9001


def make_jwt(
    *, iat: int = 0, lifetime: int = 120, sub: int = USER_ID, company: int = COMPANY_ID
) -> str:
    """An unsigned JWT with Cinode's claims. Only the payload is ever read."""

    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = {"sub": str(sub), "companySub": str(company), "iat": iat, "exp": iat + lifetime}
    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}.signature"


class FakeClock:
    """A clock that only moves when told to: call it for the time, `sleep` to advance it."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        self.sleeps.append(seconds)
        self.t += seconds


def keyword_payload(**overrides: object) -> dict[str, object]:
    """A synthetic keyword shaped like Cinode's `KeywordModel`."""
    payload: dict[str, object] = {
        "id": 22070,
        "type": 1,
        "masterSynonymId": 2930,
        "masterSynonym": "Python",
        "synonyms": ["Python 3"],
        "universal": True,
        "verified": True,
    }
    return payload | overrides


def skill_payload(**overrides: object) -> dict[str, object]:
    """A synthetic skill shaped like Cinode's `CompanyUserSkillModel`."""
    payload: dict[str, object] = {
        "companyId": COMPANY_ID,
        "companyUserId": USER_ID,
        "numberOfDaysWorkExperience": 1461,
        "profileId": 5005,
        "id": 22070,
        "level": 4,
        "levelGoal": 5,
        "levelGoalDeadline": "2027-06-30T00:00:00",
        "keyword": keyword_payload(),
        "favourite": True,
        "links": [],
    }
    return payload | overrides


def user_payload(**overrides: object) -> dict[str, object]:
    """A synthetic user shaped like Cinode's `CompanyUserBaseModel`."""
    payload: dict[str, object] = {
        "companyUserId": USER_ID,
        "companyId": COMPANY_ID,
        "seoId": "ada-example",
        "firstName": "Ada",
        "lastName": "Example",
        "companyUserType": 0,
        "id": USER_ID,
        "links": [],
    }
    return payload | overrides


def team_payload(**overrides: object) -> dict[str, object]:
    """A synthetic team shaped like Cinode's `TeamModel`."""
    payload: dict[str, object] = {
        "id": TEAM_ID,
        "companyId": COMPANY_ID,
        "name": "Example Team",
        "description": None,
        "parentTeamId": None,
        "links": [],
    }
    return payload | overrides


def member_payload(**overrides: object) -> dict[str, object]:
    """A synthetic team member shaped like Cinode's `TeamMemberModel`."""
    payload: dict[str, object] = {
        "teamId": TEAM_ID,
        "companyUserId": USER_ID,
        "companyUser": user_payload(),
        "availabilityPercent": 100,
        "links": [],
    }
    return payload | overrides
