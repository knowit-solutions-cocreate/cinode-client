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


def _translation(profile_translation_id: int, culture: str) -> dict[str, object]:
    """The `profileTranslation` Cinode nests in a profile and in each text entry."""
    return {
        "id": profile_translation_id,
        "languageBranch": {"id": 1, "language": {"languageId": 1, "culture": culture}},
    }


def profile_payload(**overrides: object) -> dict[str, object]:
    """A synthetic profile shaped like Cinode's `CompanyUserProfileFullModel`, much reduced."""
    sv, en = _translation(501, "sv-SE"), _translation(502, "en-GB")
    payload: dict[str, object] = {
        "id": 5005,
        "companyId": COMPANY_ID,
        "companyUserId": USER_ID,
        "profileTranslation": sv,
        "profileTranslations": [sv, en],
        "createdWhen": "2026-01-02T03:04:05.1234567",
        "updatedWhen": "2026-03-04T05:06:07",
        "presentation": {
            "id": 6001,
            "translations": [
                {
                    "profileTranslationId": 501,
                    "profileTranslation": sv,
                    "title": "Utvecklare",
                    "description": "Skriver kod.",
                    "personalDescription": "",
                },
                {
                    "profileTranslationId": 502,
                    "profileTranslation": en,
                    "title": "Developer",
                    "description": "Writes code.",
                    "personalDescription": "Likes tea.",
                },
            ],
        },
        "workExperience": [
            {
                "id": 7001,
                "startDate": "2024-01-01T00:00:00",
                "endDate": None,
                "isCurrent": True,
                "translations": [
                    {
                        "profileTranslationId": 501,
                        "profileTranslation": sv,
                        "employer": "Exempel AB",
                        "title": "Utvecklare",
                        "description": None,
                    }
                ],
                "skills": [
                    skill_payload(
                        changeHistory=[{"level": 3, "date": "2025-01-01T00:00:00"}],
                        translations=[{"profileTranslationId": 501}],
                    )
                ],
            }
        ],
        "education": None,
        "languages": [
            {
                "id": 8001,
                "language": {"languageId": 2, "name": "English", "culture": "en"},
                "level": 5,
            }
        ],
        "employers": [
            {
                "id": 9101,
                "startDate": "2020-01-01T00:00:00",
                "endDate": "2023-12-31T00:00:00",
                "isCurrent": None,
                "translations": [
                    {
                        "profileTranslationId": 501,
                        "profileTranslation": sv,
                        "name": "Exempel AB",
                        "title": "Konsult",
                        "description": "",
                    }
                ],
            }
        ],
        "training": [
            {
                "id": 9201,
                "trainingType": 1,
                "year": 2025,
                "expireDate": None,
                "code": "EX-1",
                "translations": [
                    {
                        "profileTranslationId": 501,
                        "profileTranslation": sv,
                        "title": "Exempelcertifikat",
                        "description": None,
                        "issuer": "Example Institute",
                        "supplier": None,
                    }
                ],
            }
        ],
        "skills": [skill_payload()],
        "references": [{"id": 9301, "firstName": "Bo"}],
        "extSkills": [{"id": 9401, "text": "Notes"}],
        "commitments": [{"id": 9501, "title": "A paper"}],
    }
    return payload | overrides
