"""
Agent Result Protocol (ARP) v1 — structured result from sub-agents.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TestSummary(BaseModel):
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class ZeusResult(BaseModel):
    """
    Mandatory output that a sub-agent must write to ``{workspace}/zeus-result.json``.
    The dispatcher reads this file after the sub-process exits to determine success.
    """

    status: str = Field(..., pattern="^(completed|failed|partial)$")
    changed_files: list[str] = Field(default_factory=list)
    test_summary: TestSummary = Field(default_factory=TestSummary)
    commit_sha: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
