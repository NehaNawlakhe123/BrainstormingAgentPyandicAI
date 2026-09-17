from __future__ import annotations

import asyncio

from .agents import BrainstormAgents
from .models import JiraEpic, StoryBreakdown


async def brainstorm_epic(
    epic: JiraEpic,
    agents: BrainstormAgents,
    max_concurrency: int,
    retrieval_context: list[str] | None = None,
):
    semaphore = asyncio.Semaphore(max_concurrency)

    async def process(story):
        async with semaphore:
            analysis = await agents.analyze_story(story)
            context = {
                "epic": epic.model_dump(mode="json"),
                "story": story.model_dump(mode="json"),
                "story_analysis": analysis.model_dump(mode="json"),
                "retrieved_context": retrieval_context or [],
            }
            gap = await agents.run(agents.gap, context)
            impact = await agents.run(agents.impact, {**context, "gap_analysis": gap.model_dump(mode="json")})
            return StoryBreakdown(story=story, story_analysis=analysis, gap_analysis=gap, impact_analysis=impact)

    breakdowns = await asyncio.gather(*(process(story) for story in epic.children))
    result = await agents.run(
        agents.orchestrator,
        {
            "epic": epic.model_dump(mode="json"),
            "story_breakdowns": [item.model_dump(mode="json") for item in breakdowns],
            "retrieved_context": retrieval_context or [],
        },
    )
    return result
