import pytest
from support import USER_ID, keyword_payload, member_payload, profile_payload, skill_payload

from cinode.models import CinodeModel, Keyword, Profile, Skill, TeamMember


def test_skill_maps_a_real_shaped_payload() -> None:
    payload = skill_payload(
        level=0, numberOfDaysWorkExperience=None, favourite=None, somethingNew="kept"
    )
    skill = Skill.parse(payload)
    assert skill.model_dump(mode="json") == {
        "keyword_id": 22070,
        "name": "Python",
        "synonym_id": 2930,
        "keyword_type": 1,
        "level": None,
        "level_goal": 5,
        "level_goal_deadline": "2027-06-30T00:00:00",
        "days_experience": 0,
        "favourite": False,
        "user_id": USER_ID,
        "is_rated": False,
        "years_experience": 0.0,
    }
    assert skill.raw["somethingNew"] == "kept"


@pytest.mark.parametrize(
    ("model", "payload", "field", "expected"),
    [
        (Skill, skill_payload(keyword=keyword_payload(masterSynonym=None)), "name", ""),
        (Keyword, keyword_payload(synonyms=None), "synonyms", []),
        (Skill, skill_payload(id=None), "keyword_id", 22070),
    ],
    ids=["masterSynonym-null", "synonyms-null", "id-null"],
)
def test_nullable_fields_fall_back(
    model: type[CinodeModel], payload: dict[str, object], field: str, expected: object
) -> None:
    assert getattr(model.parse(payload), field) == expected


@pytest.mark.parametrize(
    ("payload", "has_user"),
    [
        ({k: v for k, v in member_payload().items() if k != "companyUserId"}, True),
        (member_payload(companyUser=None), False),
        (member_payload(companyUserId=None), True),
    ],
    ids=["inline-only", "top-level-only", "top-level-null"],
)
def test_team_member_user_id_is_resolved(payload: dict[str, object], has_user: bool) -> None:
    member = TeamMember.parse(payload)
    assert member.user_id == USER_ID
    assert (member.user is not None) is has_user


def test_profile_dumps_a_lean_projection() -> None:
    profile = Profile.parse(profile_payload())
    assert profile.model_dump(mode="json") == {
        "id": 5005,
        "user_id": USER_ID,
        "language": "sv-SE",
        "created": "2026-01-02T03:04:05.123456",
        "updated": "2026-03-04T05:06:07",
        "presentation": {
            "id": 6001,
            "translations": [
                {
                    "profile_translation_id": 501,
                    "language": "sv-SE",
                    "title": "Utvecklare",
                    "description": "Skriver kod.",
                    "personal_description": "",
                },
                {
                    "profile_translation_id": 502,
                    "language": "en-GB",
                    "title": "Developer",
                    "description": "Writes code.",
                    "personal_description": "Likes tea.",
                },
            ],
        },
        "work_experience": [
            {
                "id": 7001,
                "start_date": "2024-01-01T00:00:00",
                "end_date": None,
                "is_current": True,
                "translations": [
                    {
                        "profile_translation_id": 501,
                        "language": "sv-SE",
                        "employer": "Exempel AB",
                        "title": "Utvecklare",
                        "description": None,
                    }
                ],
                "skills": [{"keyword_id": 22070, "name": "Python"}],
            }
        ],
        "education": [],
        "languages": [
            {"id": 8001, "language_id": 2, "name": "English", "culture": "en", "level": 5}
        ],
        "employers": [
            {
                "id": 9101,
                "start_date": "2020-01-01T00:00:00",
                "end_date": "2023-12-31T00:00:00",
                "is_current": False,
                "translations": [
                    {
                        "profile_translation_id": 501,
                        "language": "sv-SE",
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
                "training_type": 1,
                "year": 2025,
                "expires": None,
                "code": "EX-1",
                "translations": [
                    {
                        "profile_translation_id": 501,
                        "language": "sv-SE",
                        "title": "Exempelcertifikat",
                        "description": None,
                        "issuer": "Example Institute",
                        "supplier": None,
                    }
                ],
            }
        ],
    }
    assert profile.created is not None and profile.created.tzinfo is None
    assert profile.raw["skills"]
