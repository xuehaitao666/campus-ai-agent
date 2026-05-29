"""Pre-built SkillRegistry instance for Campus AI Agent."""

from skills.base import SkillRegistry
from skills.definitions import BUILTIN_SKILLS

default_registry = SkillRegistry(BUILTIN_SKILLS)
