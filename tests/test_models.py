import pytest
from support import USER_ID, keyword_payload, member_payload, skill_payload

from cinode.models import CinodeModel, Keyword, Skill, TeamMember


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
