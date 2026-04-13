"""
ZeusOpen v3 configuration loader.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ZeusConfig:
    def __init__(self, project_root: Path, version: str = "v3") -> None:
        self.project_root = Path(project_root)
        self.version = version
        self._config_path = self.project_root / ".zeus" / version / "config.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with open(self._config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    @property
    def project_name(self) -> str:
        return self._data.get("project", {}).get("name", "ZeusOpen Project")

    @property
    def north_star(self) -> str:
        return self._data.get("metrics", {}).get("north_star", "N/A")

    @property
    def subagent(self) -> dict[str, Any]:
        return self._data.get("subagent", {})

    @property
    def dispatcher_mode(self) -> str:
        return self.subagent.get("dispatcher", "auto")

    @property
    def dispatcher_timeout(self) -> float:
        return float(self.subagent.get("timeout_seconds", 600.0))

    @property
    def bootstrap_files(self) -> list[str]:
        default = ["AGENTS.md", "USER.md", "IDENTITY.md", "SOUL.md"]
        return self.subagent.get("bootstrap", {}).get("files", default)

    @property
    def workspace_backend(self) -> str:
        return self._data.get("workspace", {}).get("backend", "copytree")

    def raw(self) -> dict[str, Any]:
        return self._data
