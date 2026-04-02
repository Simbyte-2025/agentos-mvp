from __future__ import annotations

import yaml
from pathlib import Path

from agentos.config.schema import AgentsConfig, ProfilesConfig


def load_agents_config(path: str = "config/agents.yaml") -> AgentsConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AgentsConfig(**data)


def load_profiles_config(path: str = "config/profiles.yaml") -> ProfilesConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ProfilesConfig.from_dict(data or {})
