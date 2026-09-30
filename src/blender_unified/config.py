"""Explicit, local process configuration. No shell evaluation or secret files."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EngineConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    required: bool = True
    timeout: float = 300


@dataclass(frozen=True)
class Config:
    engines: list[EngineConfig]
    priority: list[str] = field(
        default_factory=lambda: ["blend_ai", "secure", "lab", "community"]
    )
    routes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path):
        data = json.loads(path.read_text())
        engines = [EngineConfig(**item) for item in data["engines"]]
        names = [e.name for e in engines]
        if not engines or len(names) != len(set(names)):
            raise ValueError("Configure at least one engine, with unique names")
        for e in engines:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", e.name):
                raise ValueError(f"Invalid engine name: {e.name}")
            if not e.command or e.timeout <= 0:
                raise ValueError(f"Invalid command or timeout for {e.name}")
        for backend in data.get("routes", {}).values():
            if backend not in names:
                raise ValueError(f"Route refers to unconfigured engine: {backend}")
        return cls(engines, data.get("priority", names), data.get("routes", {}))
