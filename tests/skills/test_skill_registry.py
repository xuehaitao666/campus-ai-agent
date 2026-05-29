"""Tests for Skill Layer v0.1 — metadata loading and validation."""

import pytest

from core.router import RouteIntent
from skills.base import SkillExample, SkillMetadata, SkillRegistry
from skills.definitions import BUILTIN_SKILLS
from skills.registry import default_registry


# ---------------------------------------------------------------------------
# 1. All built-in skills load successfully
# ---------------------------------------------------------------------------

def test_all_builtin_skills_load_successfully():
    """All built-in skills can be loaded from the default registry."""
    skills = default_registry.list_skills()

    assert len(skills) == 4, f"Expected 3 built-in skills, got {len(skills)}"
    skill_names = {skill.name for skill in skills}
    assert skill_names == {"course_query", "event_query", "policy_qa", "study_plan"}


# ---------------------------------------------------------------------------
# 2. No duplicate skill names
# ---------------------------------------------------------------------------

def test_no_duplicate_skill_names():
    """Built-in skill names are unique."""
    names = [skill.name for skill in BUILTIN_SKILLS]
    assert len(names) == len(set(names)), f"Duplicate skill names found: {names}"


# ---------------------------------------------------------------------------
# 3. course_query_skill field completeness
# ---------------------------------------------------------------------------

def test_course_query_skill_has_all_required_fields():
    """course_query_skill has complete and valid metadata."""
    skill = default_registry.get_skill("course_query")

    assert skill.name == "course_query"
    assert skill.intent == RouteIntent.COURSE.value
    assert len(skill.trigger_keywords) > 0, "trigger_keywords must not be empty"
    assert any(
        keyword in skill.trigger_keywords for keyword in ("课程", "课表")
    ), "trigger_keywords should contain '课程' or '课表'"

    assert skill.fast_path_enabled is True
    assert skill.fast_path_handler_name == "_maybe_handle_course_fast_path"

    assert "get_course_schedule" in skill.bound_tools
    assert skill.response_template_name == "format_course_fast_path_response"

    assert len(skill.examples) > 0, "examples must not be empty"
    assert skill.examples[0].query, "first example must have a query"


# ---------------------------------------------------------------------------
# 4. event_query_skill field completeness
# ---------------------------------------------------------------------------

def test_event_query_skill_has_all_required_fields():
    """event_query_skill has complete and valid metadata."""
    skill = default_registry.get_skill("event_query")

    assert skill.name == "event_query"
    assert skill.intent == RouteIntent.EVENT.value
    assert len(skill.trigger_keywords) > 0, "trigger_keywords must not be empty"
    assert any(
        keyword in skill.trigger_keywords for keyword in ("讲座", "活动")
    ), "trigger_keywords should contain '讲座' or '活动'"

    assert skill.fast_path_enabled is True
    assert skill.fast_path_handler_name == "_maybe_handle_event_fast_path"

    assert "get_campus_events" in skill.bound_tools
    assert skill.response_template_name == "format_event_fast_path_response"

    assert len(skill.examples) > 0, "examples must not be empty"
    assert skill.examples[0].query, "first example must have a query"


# ---------------------------------------------------------------------------
# 5. Duplicate names raise ValueError
# ---------------------------------------------------------------------------

def test_duplicate_skill_names_raise_error():
    """SkillRegistry raises ValueError when two skills share the same name."""
    skill_a = SkillMetadata(
        name="dup",
        display_name="A",
        description="desc",
        intent="general_chat",
        trigger_keywords=["hello"],
        bound_tools=["Calculator"],
    )
    skill_b = SkillMetadata(
        name="dup",
        display_name="B",
        description="desc",
        intent="general_chat",
        trigger_keywords=["world"],
        bound_tools=["Calculator"],
    )

    with pytest.raises(ValueError, match="Duplicate"):
        SkillRegistry([skill_a, skill_b])


# ---------------------------------------------------------------------------
# 6. Unknown skill raises KeyError
# ---------------------------------------------------------------------------

def test_get_unknown_skill_raises_key_error():
    """get_skill raises KeyError for an unregistered skill name."""
    with pytest.raises(KeyError, match="unknown_skill"):
        default_registry.get_skill("unknown_skill")


# ---------------------------------------------------------------------------
# 7. has_skill returns correct booleans
# ---------------------------------------------------------------------------

def test_has_skill_returns_correct_booleans():
    """has_skill returns True for registered skills and False otherwise."""
    assert default_registry.has_skill("course_query") is True
    assert default_registry.has_skill("event_query") is True
    assert default_registry.has_skill("nonexistent") is False


# ---------------------------------------------------------------------------
# 8. fast_path_enabled requires handler name
# ---------------------------------------------------------------------------

def test_fast_path_enabled_requires_handler_name():
    """Pydantic validation rejects fast_path_enabled=True without handler."""
    with pytest.raises(ValueError, match="fast_path_handler_name"):
        SkillMetadata(
            name="bad_skill",
            display_name="Bad",
            description="desc",
            intent="general_chat",
            trigger_keywords=["hello"],
            bound_tools=["Calculator"],
            fast_path_enabled=True,
            fast_path_handler_name=None,
        )


# ---------------------------------------------------------------------------
# 9. Empty required string fields are rejected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name,field_value",
    [
        ("name", ""),
        ("display_name", ""),
        ("description", ""),
        ("intent", ""),
    ],
)
def test_empty_required_string_fields_are_rejected(field_name, field_value):
    """Pydantic validation rejects empty required string fields."""
    kwargs = {
        "name": "valid_name",
        "display_name": "Valid Display",
        "description": "Valid description.",
        "intent": "general_chat",
        "trigger_keywords": ["hello"],
        "bound_tools": ["Calculator"],
    }
    kwargs[field_name] = field_value

    with pytest.raises(ValueError, match=f"SkillMetadata.{field_name}"):
        SkillMetadata(**kwargs)
