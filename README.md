# Jira Epic Brainstorming Agent

# Jira Epic Brainstorming Agent

This implementation provides a Pydantic AI-only multi-agent workflow with Jira,
SQLite, JSONL audit logs, and ChromaDB retrieval:

1. The story analyzer evaluates each story's narrative and completeness.
2. The gap analyzer checks requirements and cross-story context.
3. The impact analyzer assesses dependencies, risks, resources, and timelines.
4. The parent orchestrator synthesizes the analyses into a validated
   `OrchestratedOutput`.

Independent stories run concurrently, while each story remains strictly ordered
as Story Analyzer -> Gap Analyzer -> Impact Analyzer.

## Commands

Install the package from this directory:

```bash
pip install -e .
```

Analyze a local epic JSON without Jira credentials:

```bash
python -m brainstorming_agent.cli analyze EPIC-123 --input epic.json
```

Use Jira Cloud retrieval:

```bash
python -m brainstorming_agent.cli analyze EPIC-123
```

`analyze` reuses the latest completed result for the Jira key. Force a fresh Jira
fetch and analysis with:

```bash
python -m brainstorming_agent.cli re-analyze EPIC-123
```

Review and explicitly approve posting the latest result as a Jira comment:

```bash
python -m brainstorming_agent.cli post_analysis EPIC-123
```

Index repository source and documentation into ChromaDB:

```bash
python -m brainstorming_agent.cli ingest-repository --path .
```

Results are stored in SQLite, execution events in `data/logs/events.jsonl`, and
retrieval documents in `data/chroma`. These paths are configurable through
environment variables.

Agent boundaries and quality rules live in the versioned files under
[`skills/`](skills/):

- [`story_analyzer.md`](skills/story_analyzer.md)
- [`gap_analyzer.md`](skills/gap_analyzer.md)
- [`impact_analyzer.md`](skills/impact_analyzer.md)
- [`orchestrator.md`](skills/orchestrator.md)

The Python wrappers validate required story fields before model calls, preserve
the sequential workflow, validate structured outputs through Pydantic AI, and
retry bounded transient failures up to three times. The workflow does not modify
the source Jira models.

## Run it

From this directory, install the example's dependency and set an OpenAI key:

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
python brainstorming_agent.py
```

On Windows PowerShell:

```powershell
pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key"
python brainstorming_agent.py
```

Set `BRAINSTORMING_MODEL` to use a different Pydantic AI model, for example
`openai:gpt-4.1-mini`.

For Jira retrieval and posting, configure `JIRA_BASE_URL`, `JIRA_EMAIL`, and
`JIRA_API_TOKEN`. Never commit the token or place it in logs. See
[`.env.example`](.env.example) for all settings.
