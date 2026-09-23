from support import USER_ID, skill_payload

from cinode.models import Skill


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
