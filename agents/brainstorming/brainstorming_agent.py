"""Sequential multi-agent analysis of a Jira epic.

Set OPENAI_API_KEY before running this example. The model can be changed with
the BRAINSTORMING_MODEL environment variable.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent


MODEL = os.getenv("BRAINSTORMING_MODEL", "openai:gpt-4.1-mini")
MAX_ATTEMPTS = 3
SKILLS_DIR = Path(__file__).parent / "skills"
RiskScore = Annotated[float, Field(ge=0, le=1)]


class JiraStory(BaseModel):
    """An individual Jira story."""

    story_key: str
    summary: str
    description: str
    acceptance_criteria: str
    status: str
    story_points: int | None = None
    assignee: str | None = None
    labels: list[str] = Field(default_factory=list)


class JiraEpic(BaseModel):
    """A Jira epic and the stories it contains."""

    epic_key: str
    summary: str
    description: str
    status: str
    priority: str
    children: list[JiraStory] = Field(default_factory=list)


class StoryAnalysis(BaseModel):
    """Narrative and completeness analysis for one story."""

    story_key: str
    narrative_structure: str
    character_arcs: list[str]
    conflict_type: str
    thematic_elements: list[str]
    pacing_issues: list[str]
    emotional_beat: str
    completeness_score: float = Field(ge=0, le=1)


class GapAnalysis(BaseModel):
    """Requirement and context gaps for one story."""

    story_key: str
    identified_gaps: list[dict[str, str]]
    missing_context: list[str]
    inconsistency_areas: list[str]
    dependency_issues: list[str]
    requirement_gaps: list[str]
    clarity_score: float = Field(ge=0, le=1)


class ImpactAnalysis(BaseModel):
    """Downstream effects and risks for one story."""

    story_key: str
    dependency_impact: dict[str, list[str]]
    downstream_effects: list[str]
    risk_assessment: dict[str, RiskScore]
    resource_implications: dict[str, int]
    timeline_constraints: list[str]
    business_value_impact: float = Field(ge=0, le=100)
    technical_debt_impact: float = Field(ge=0, le=100)


class OrchestratedOutput(BaseModel):
    """Controlled, team-facing output from the parent orchestrator."""

    epic_summary: dict[str, Any] = Field(
        description="Overall epic health and status"
    )
    story_breakdowns: list[dict[str, Any]] = Field(
        description="Individual story analyses"
    )
    critical_issues: list[dict[str, Any]] = Field(
        description="Critical blockers and issues"
    )
    recommendations: list[dict[str, Any]] = Field(
        description="Actionable recommendations"
    )
    confidence_scores: dict[str, float] = Field(
        description="Confidence in each analysis"
    )
    next_steps: list[str] = Field(description="Suggested immediate actions")


def validate_story_data(story: dict[str, Any]) -> str:
    """Validate required fields before an LLM call."""
    parsed = JiraStory.model_validate(story)
    missing = []
    if not parsed.summary.strip():
        missing.append("summary")
    if not parsed.acceptance_criteria.strip():
        missing.append("acceptance_criteria")
    if missing:
        raise ValueError(
            f"{parsed.story_key}: required fields are empty: {', '.join(missing)}"
        )
    return f"{parsed.story_key}: story data is valid"


def check_completeness(story: dict[str, Any]) -> str:
    """Report deterministic completeness warnings for the story analyzer."""
    parsed = JiraStory.model_validate(story)
    warnings = []
    if not parsed.description.strip():
        warnings.append("description is missing")
    if not parsed.acceptance_criteria.strip():
        warnings.append("acceptance criteria is missing")
    return (
        f"{parsed.story_key}: " + "; ".join(warnings)
        if warnings
        else f"{parsed.story_key}: no basic completeness warnings"
    )


def _skills(name: str) -> str:
    path = SKILLS_DIR / name
    return path.read_text(encoding="utf-8")


async def _run_with_retry(agent: Agent[Any, Any], payload: Any) -> Any:
    """Retry transient agent failures without hiding the final error."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return (await asyncio.wait_for(agent.run(payload), timeout=30)).output
        except (TimeoutError, OSError, ValueError) as error:
            last_error = error
            if attempt == MAX_ATTEMPTS:
                break
            await asyncio.sleep(attempt)
    raise RuntimeError(
        f"Agent failed after {MAX_ATTEMPTS} attempts"
    ) from last_error


class StoryAnalyzerAgent:
    def __init__(self) -> None:
        self.agent = Agent(
            MODEL,
            output_type=StoryAnalysis,
            tools=[validate_story_data, check_completeness],
            instructions=_skills("story_analyzer.md"),
        )

    async def analyze_story(self, story: JiraStory) -> StoryAnalysis:
        validate_story_data(story.model_dump(mode="json"))
        return await _run_with_retry(self.agent, story.model_dump(mode="json"))


class GapAnalyzerAgent:
    def __init__(self) -> None:
        self.agent = Agent(
            MODEL,
            output_type=GapAnalysis,
            instructions=_skills("gap_analyzer.md"),
        )

    async def analyze(self, context: dict[str, Any]) -> GapAnalysis:
        return await _run_with_retry(self.agent, context)


class ImpactAnalyzerAgent:
    def __init__(self) -> None:
        self.agent = Agent(
            MODEL,
            output_type=ImpactAnalysis,
            instructions=_skills("impact_analyzer.md"),
        )

    async def analyze(self, context: dict[str, Any]) -> ImpactAnalysis:
        return await _run_with_retry(self.agent, context)


story_analyzer = StoryAnalyzerAgent()
gap_analyzer = GapAnalyzerAgent()
impact_analyzer = ImpactAnalyzerAgent()
orchestrator_agent = Agent(
    MODEL,
    output_type=OrchestratedOutput,
    instructions=_skills("orchestrator.md"),
)


async def brainstorm_epic(epic_data: JiraEpic) -> OrchestratedOutput:
    """Analyze an epic sequentially and synthesize a validated final result."""
    story_breakdowns: list[dict[str, Any]] = []
    epic_context = epic_data.model_dump(mode="json")

    for story in epic_data.children:
        story_analysis = await story_analyzer.analyze_story(story)
        breakdown: dict[str, Any] = {
            "story": story.model_dump(mode="json"),
            "story_analysis": story_analysis.model_dump(mode="json"),
        }

        gap_analysis = await gap_analyzer.analyze({"epic": epic_context, **breakdown})
        breakdown["gap_analysis"] = gap_analysis.model_dump(mode="json")

        impact_analysis = await impact_analyzer.analyze(
            {"epic": epic_context, **breakdown}
        )
        breakdown["impact_analysis"] = impact_analysis.model_dump(mode="json")
        story_breakdowns.append(breakdown)

    synthesis_input = {
        "epic": epic_context,
        "story_breakdowns": story_breakdowns,
    }
    return await _run_with_retry(orchestrator_agent, synthesis_input)


def sample_epic() -> JiraEpic:
    """Return a small epic that can be used to try the example."""
    return JiraEpic(
        epic_key="EPIC-123",
        summary="User Authentication Redesign",
        description="Redesign authentication to support OAuth 2.0 and SSO.",
        status="In Progress",
        priority="High",
        children=[
            JiraStory(
                story_key="STORY-1",
                summary="Implement OAuth 2.0 login flow",
                description="Allow users to authenticate with supported identity providers.",
                acceptance_criteria=(
                    "Users can log in with Google or GitHub; failed logins show "
                    "an actionable error."
                ),
                status="To Do",
                story_points=8,
                assignee="dev_team_lead",
                labels=["authentication", "oauth"],
            ),
            JiraStory(
                story_key="STORY-2",
                summary="Add single sign-on for enterprise customers",
                description="Support SAML-based SSO for enterprise tenants.",
                acceptance_criteria=(
                    "An administrator can configure an identity provider and "
                    "users can sign in through the configured provider."
                ),
                status="To Do",
                story_points=13,
                labels=["authentication", "sso"],
            ),
        ],
    )


async def main() -> None:
    result = await brainstorm_epic(sample_epic())
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
