"""
Subagent dispatcher abstraction for ZeusOpen v3.
"""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Any


class SubagentDispatcher(abc.ABC):
    """Responsible for executing a task in an isolated workspace."""

    @abc.abstractmethod
    async def run(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
    ) -> dict[str, Any]:
        """
        Execute the task and return a dict compatible with ZeusResult.
        The worker will read {workspace}/zeus-result.json as the primary source of truth.
        """
        raise NotImplementedError
