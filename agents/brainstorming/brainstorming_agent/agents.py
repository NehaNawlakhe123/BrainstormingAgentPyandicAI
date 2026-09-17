from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic_ai import Agent

from .config import Settings
from .audit_logger import AuditLogger
from .models import GapAnalysis, ImpactAnalysis, JiraStory, OrchestratedOutput, StoryAnalysis

T = TypeVar("T")


def skill(name: str) -> str:
    return (Path(__file__).parents[1] / "skills" / name).read_text(encoding="utf-8")


class BrainstormAgents:
    def __init__(self, settings: Settings, audit: AuditLogger | None = None):
        self.settings = settings
        self.audit = audit
        self.story = Agent(settings.model, output_type=StoryAnalysis, instructions=skill("story_analyzer.md"))
        self.gap = Agent(settings.model, output_type=GapAnalysis, instructions=skill("gap_analyzer.md"))
        self.impact = Agent(settings.model, output_type=ImpactAnalysis, instructions=skill("impact_analyzer.md"))
        self.orchestrator = Agent(settings.model, output_type=OrchestratedOutput, instructions=skill("orchestrator.md"))

    def _offline_output(self, agent: Agent[Any, T], prompt: Any) -> T:
        if agent is self.story:
            story = prompt if isinstance(prompt, dict) else {}
            key = story.get("story_key") or "STORY-UNKNOWN"
            return cast(T, StoryAnalysis(
                story_key=key,
                narrative_structure="Offline fallback analysis: clear narrative with defined problem, user goal, and success conditions.",
                character_arcs=["Primary user identifies the problem", "User completes the required journey", "User recovers from failure states"],
                conflict_type="workflow friction and missing trust signals",
                thematic_elements=["trust", "clarity", "reliability"],
                pacing_issues=["Needs explicit edge-case validation"],
                emotional_beat="The user feels confident once the path is obvious and safe.",
                completeness_score=0.82,
            ))
        if agent is self.gap:
            return GapAnalysis(
                story_key=(prompt.get("story", {}).get("story_key") if isinstance(prompt, dict) else "STORY-UNKNOWN"),
                identified_gaps=[{"area": "acceptance criteria", "detail": "Offline fallback assumes gap validation is needed until explicit scenarios are confirmed."}],
                missing_context=["No additional business constraints were supplied in the local run"],
                inconsistency_areas=[],
                dependency_issues=["Cross-story dependency should be confirmed in Jira"],
                requirement_gaps=["Offline fallback has not validated all edge conditions"],
                clarity_score=0.74,
            ) as T
        if agent is self.impact:
            return ImpactAnalysis(
                story_key=(prompt.get("story", {}).get("story_key") if isinstance(prompt, dict) else "STORY-UNKNOWN"),
                dependency_impact={"upstream": ["Requires validation against related stories"], "downstream": ["May affect rollout sequencing"]},
                downstream_effects=["Release dependency checks may be needed"],
                risk_assessment={"business": 0.48, "technical": 0.52, "operational": 0.41},
                resource_implications={"engineering": 1, "qa": 1},
                timeline_constraints=["Timeline depends on final requirement validation"],
                business_value_impact=76.0,
                technical_debt_impact=34.0,
            ) as T
        if agent is self.orchestrator:
            epic = prompt.get("epic", {}) if isinstance(prompt, dict) else {}
            stories = prompt.get("story_breakdowns", []) if isinstance(prompt, dict) else []
            return OrchestratedOutput(
                epic_summary={"status": "yellow", "health": "Needs final validation", "epic_key": epic.get("epic_key", "UNKNOWN")},
                story_breakdowns=[item for item in stories],
                critical_issues=[{"severity": "medium", "story": "Offline validation only", "issue": "Model execution was simulated because no LLM API key is configured."}],
                recommendations=[{"priority": "medium", "action": "Add OPENAI_API_KEY and rerun for live model analysis."}],
                confidence_scores={"story_analysis": 0.82, "gap_analysis": 0.74, "impact_analysis": 0.75, "orchestrator": 0.8},
                next_steps=["Configure API key", "Re-run with live model", "Review Jira comments before posting"],
            ) as T
        raise RuntimeError(f"No offline mock is defined for agent {type(agent).__name__}")

    async def run(self, agent: Agent[Any, T], prompt: Any) -> T:
        last: Exception | None = None
        agent_name = getattr(agent, "name", None) or "pydantic_ai_agent"
        if not any(os.getenv(key) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")) and os.getenv("BRAINSTORMING_FORCE_LIVE") is None:
            if self.audit:
                self.audit.write("offline_mode", agent=agent_name)
            return self._offline_output(agent, prompt)
        for attempt in range(self.settings.max_retries):
            try:
                if self.audit:
                    self.audit.write("agent_started", agent=agent_name, attempt=attempt + 1)
                return (await asyncio.wait_for(agent.run(prompt), self.settings.timeout_seconds)).output
            except (TimeoutError, OSError, RuntimeError, ValueError) as error:
                last = error
                if self.audit:
                    self.audit.write("agent_failed", agent=agent_name, attempt=attempt + 1, error=str(error))
                if attempt + 1 == self.settings.max_retries:
                    raise
                await asyncio.sleep(attempt + 1)
        raise RuntimeError("agent retry loop exhausted") from last

    async def analyze_story(self, story: JiraStory) -> StoryAnalysis:
        if not story.summary.strip() or not story.acceptance_criteria.strip():
            raise ValueError(f"{story.story_key} requires summary and acceptance criteria")
        return await self.run(self.story, story.model_dump(mode="json"))
