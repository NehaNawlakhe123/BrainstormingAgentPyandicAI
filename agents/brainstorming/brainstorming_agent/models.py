from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ImpactScore = Field(ge=0, le=100)


class JiraStory(BaseModel):
    story_key: str
    summary: str
    description: str = ""
    acceptance_criteria: str = ""
    status: str = ""
    story_points: int | None = None
    assignee: str | None = None
    labels: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class JiraEpic(BaseModel):
    epic_key: str
    summary: str
    description: str = ""
    status: str = ""
    priority: str = ""
    updated_at: datetime | None = None
    children: list[JiraStory] = Field(default_factory=list)

    @field_validator("epic_key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*-\d+", value):
            raise ValueError("epic_key must look like PROJ-123")
        return value


class StoryAnalysis(BaseModel):
    story_key: str
    narrative_structure: str
    character_arcs: list[str]
    conflict_type: str
    thematic_elements: list[str]
    pacing_issues: list[str]
    emotional_beat: str
    completeness_score: float = Field(ge=0, le=1)


class GapAnalysis(BaseModel):
    story_key: str
    identified_gaps: list[dict[str, str]]
    missing_context: list[str]
    inconsistency_areas: list[str]
    dependency_issues: list[str]
    requirement_gaps: list[str]
    clarity_score: float = Field(ge=0, le=1)


class ImpactAnalysis(BaseModel):
    story_key: str
    dependency_impact: dict[str, list[str]]
    downstream_effects: list[str]
    risk_assessment: dict[str, float] = Field(default_factory=dict)
    resource_implications: dict[str, int]
    timeline_constraints: list[str]
    business_value_impact: float = ImpactScore
    technical_debt_impact: float = ImpactScore


class StoryBreakdown(BaseModel):
    story: JiraStory
    story_analysis: StoryAnalysis
    gap_analysis: GapAnalysis
    impact_analysis: ImpactAnalysis


class OrchestratedOutput(BaseModel):
    epic_summary: dict[str, Any]
    story_breakdowns: list[StoryBreakdown]
    critical_issues: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    confidence_scores: dict[str, float]
    next_steps: list[str]


class AnalysisRecord(BaseModel):
    analysis_id: str
    jira_key: str
    source_hash: str
    status: Literal["running", "completed", "approved", "posted", "failed", "superseded"]
    created_at: datetime
    completed_at: datetime | None = None
    output: OrchestratedOutput | None = None
    error: str | None = None


class CommandRequest(BaseModel):
    command: Literal["analyze", "post_analysis", "re-analyze"]
    jira_key: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
