"""Skill Layer base types and registry for Campus AI Agent."""

from pydantic import BaseModel, Field, model_validator


class SkillExample(BaseModel):
    """A single input/output example for a Skill, used for testing and documentation."""

    query: str = Field(description="Example user input that should trigger this Skill.")
    expected_intent: str = Field(
        description="Expected RouteIntent value, e.g. 'course_schedule'.",
    )
    expected_params: dict[str, str | None] = Field(
        default_factory=dict,
        description="Expected parameters extracted from the query.",
    )


class SkillMetadata(BaseModel):
    """Minimal metadata describing one Campus Skill.

    Each Skill corresponds to a supported user intent (course query, event query,
    policy QA, study planner, etc.) and records the functions, tools, keywords,
    and templates that currently implement it.
    """

    # --- Identity ---
    name: str = Field(description="Unique skill identifier, e.g. 'course_query'.")
    display_name: str = Field(description="Human-readable name, e.g. '课程查询'.")
    description: str = Field(description="One-sentence description of the skill.")
    version: str = Field(default="1.0.0", description="Semantic version string.")

    # --- Routing ---
    intent: str = Field(description="RouteIntent value, e.g. 'course_schedule'.")
    trigger_keywords: list[str] = Field(
        description="Keywords that trigger this skill.",
        min_length=1,
    )

    # --- Fast path ---
    fast_path_enabled: bool = Field(
        default=False,
        description="Whether this skill can bypass the LLM via a fast-path handler.",
    )
    fast_path_handler_name: str | None = Field(
        default=None,
        description="Name of the _maybe_handle_*_fast_path function in service.py.",
    )

    # --- Tools ---
    bound_tools: list[str] = Field(
        description="LangChain tool names bound to this skill.",
        min_length=1,
    )
    input_schema: dict[str, str] = Field(
        default_factory=dict,
        description="Tool input parameter name -> type hint, e.g. {'day': 'str | None'}.",
    )

    # --- Output ---
    output_format: str = Field(
        default="structured_markdown",
        description="Output format: 'structured_markdown', 'json', or 'plain_text'.",
    )
    response_template_name: str | None = Field(
        default=None,
        description="Formatting function name in core.response_templates.",
    )

    # --- Test & documentation ---
    examples: list[SkillExample] = Field(
        default_factory=list,
        description="Example queries with expected intent and parameters.",
    )

    @model_validator(mode="after")
    def _validate_fast_path_consistency(self) -> "SkillMetadata":
        if self.fast_path_enabled and self.fast_path_handler_name is None:
            raise ValueError(
                f"Skill '{self.name}': fast_path_enabled=True requires "
                "fast_path_handler_name to be set."
            )
        return self

    @model_validator(mode="after")
    def _validate_required_strings(self) -> "SkillMetadata":
        for attr in ("name", "display_name", "description", "intent"):
            value = getattr(self, attr)
            if not value or not value.strip():
                raise ValueError(f"SkillMetadata.{attr} must not be empty.")
        return self


class SkillRegistry:
    """Thread-safe in-memory registry of Campus Skills."""

    def __init__(self, skills: list[SkillMetadata]) -> None:
        seen: set[str] = set()
        duplicates: list[str] = []
        for skill in skills:
            if skill.name in seen:
                duplicates.append(skill.name)
            seen.add(skill.name)
        if duplicates:
            raise ValueError(
                f"Duplicate skill names detected: {duplicates}. "
                "Each Skill must have a unique 'name'."
            )
        self._skills: dict[str, SkillMetadata] = {skill.name: skill for skill in skills}

    def list_skills(self) -> list[SkillMetadata]:
        """Return all registered skills."""
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillMetadata:
        """Return a skill by name, raising KeyError if not found."""
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not found in registry.")
        return self._skills[name]

    def has_skill(self, name: str) -> bool:
        """Check whether a skill is registered."""
        return name in self._skills
