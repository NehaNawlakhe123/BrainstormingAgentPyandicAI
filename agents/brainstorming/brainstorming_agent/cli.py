from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .models import JiraEpic
from .service import AnalysisService
from .config import Settings
from .repository_ingest import ingest_repository
from .vector_store import VectorStore


async def execute(args: argparse.Namespace) -> None:
    if args.command == "ingest-repository":
        count = ingest_repository(Path(args.path), VectorStore(Settings().chroma_path))
        print(json.dumps({"indexed_files": count}))
        return
    service = AnalysisService()
    if args.command == "post_analysis":
        print(json.dumps({"comment_id": await service.post_analysis(args.jira_key)}))
        return
    epic = None
    if args.input:
        epic = JiraEpic.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
    output = await service.analyze(args.jira_key, refresh=args.command == "re-analyze", epic=epic)
    print(output.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pydantic AI Jira brainstorming agent")
    parser.add_argument("command", choices=["analyze", "post_analysis", "re-analyze", "ingest-repository"])
    parser.add_argument("jira_key", nargs="?")
    parser.add_argument("--input", help="Local Jira epic JSON; avoids Jira retrieval")
    parser.add_argument("--path", default=".", help="Repository root for ingest-repository")
    asyncio.run(execute(parser.parse_args()))


if __name__ == "__main__":
    main()
