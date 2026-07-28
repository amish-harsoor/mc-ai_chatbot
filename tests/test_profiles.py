"""Unit tests for condensed session/profile helpers (no DB required)."""

from src.db.profiles import (
    PREF_COURSES,
    PREF_DEPARTMENT,
    PREF_EXPERIENCE,
    PREF_GOAL,
    PREF_TOPICS,
    _session_row_to_dict,
    empty_prefs,
    expand_prefs,
    extract_prefs_from_metadata,
    merge_prefs,
    resolve_owner,
)


def test_resolve_owner_prefers_registered():
    owner_id, owner_type = resolve_owner(user_id="user-1", guest_id="guest_x")
    assert owner_id == "user-1"
    assert owner_type == "registered"


def test_resolve_owner_guest():
    owner_id, owner_type = resolve_owner(guest_id="guest_abc")
    assert owner_id == "guest_abc"
    assert owner_type == "guest"


def test_merge_prefs_condensed_keys():
    prefs = merge_prefs(
        empty_prefs(),
        experience="Entry-level",
        department="Finance",
        goal="Promotion",
        course_ids=["4606"],
        topics=["budgeting"],
    )
    assert prefs[PREF_EXPERIENCE] == "Entry-level"
    assert prefs[PREF_DEPARTMENT] == "Finance"
    assert prefs[PREF_GOAL] == "Promotion"
    assert prefs[PREF_COURSES] == ["4606"]
    assert prefs[PREF_TOPICS] == ["budgeting"]

    expanded = expand_prefs(prefs)
    assert expanded["experience"] == "Entry-level"
    assert expanded["department"] == "Finance"
    assert expanded["course_ids"] == ["4606"]
    assert expanded["profile_complete"] is True


def test_extract_prefs_from_onboarding_metadata():
    prefs = extract_prefs_from_metadata(
        {
            "step": "goal",
            "profile_complete": True,
            "profile": {
                "experience": "Mid-level",
                "department": "IT",
                "goal": "Certification",
            },
        }
    )
    assert prefs[PREF_EXPERIENCE] == "Mid-level"
    assert prefs[PREF_DEPARTMENT] == "IT"
    assert prefs[PREF_GOAL] == "Certification"


def test_extract_prefs_from_step_value():
    prefs = extract_prefs_from_metadata(
        {"step": "experience", "value": "Senior/Manager (8+ years)", "type": "onboarding_selection"}
    )
    assert prefs[PREF_EXPERIENCE] == "Senior/Manager (8+ years)"


def test_merge_prefs_dedupes_courses_and_topics():
    base = merge_prefs(None, course_ids=["1", "2"], topics=["a"])
    merged = merge_prefs(base, course_ids=["2", "3"], topics=["a", "b"])
    assert merged[PREF_COURSES] == ["1", "2", "3"]
    assert merged[PREF_TOPICS] == ["a", "b"]


def test_session_row_maps_legacy_user_id_only():
    """Old chat_sessions rows only had user_id — must not KeyError on owner_id."""
    row = {
        "session_id": "sid-1",
        "user_id": "reg-9",
        "created_at": None,
        "updated_at": None,
    }
    data = _session_row_to_dict(row)
    assert data["owner_id"] == "reg-9"
    assert data["owner_type"] == "registered"
    assert data["prefs"] == {}
    assert data["stats"]["n"] == 0


def test_session_row_maps_missing_owner_to_guest():
    row = {"session_id": "sid-2"}
    data = _session_row_to_dict(row)
    assert data["owner_id"] == "guest_sid-2"
    assert data["owner_type"] == "guest"
