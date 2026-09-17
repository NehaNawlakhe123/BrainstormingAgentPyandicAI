from __future__ import annotations

from uuid import uuid4

from .agents import BrainstormAgents
from .audit_logger import AuditLogger
from .config import Settings
from .jira_client import JiraClient
from .models import JiraEpic, OrchestratedOutput
from .orchestrator import brainstorm_epic
from .persistence import LearningStore


class AnalysisService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.store = LearningStore(self.settings.sqlite_path)
        self.audit = AuditLogger(self.settings.log_path)
        self.agents = BrainstormAgents(self.settings, self.audit)
        self.vector = None
        try:
            from .vector_store import VectorStore
            self.vector = VectorStore(self.settings.chroma_path)
        except RuntimeError:
            self.audit.write("vector_store_unavailable")

    async def analyze(self, jira_key: str, refresh: bool = False, epic: JiraEpic | None = None) -> OrchestratedOutput:
        if not refresh:
            cached = self.store.latest(jira_key)
            if cached and cached.output:
                self.audit.write("analysis_reused", jira_key=jira_key, analysis_id=cached.analysis_id)
                return cached.output
        current = epic or await JiraClient(self.settings).get_epic_with_children(jira_key)
        retrieval_context = []
        if self.vector:
            retrieval_context = self.vector.search(f"{current.epic_key} {current.summary}")
        analysis_id = str(uuid4())
        self.store.supersede(jira_key) if refresh else None
        self.store.begin(analysis_id, jira_key, self.store.source_hash(current))
        self.store.save_snapshot(analysis_id, current)
        self.audit.write("analysis_started", jira_key=jira_key, analysis_id=analysis_id, refresh=refresh)
        try:
            output = await brainstorm_epic(
                current, self.agents, self.settings.max_concurrency, retrieval_context
            )
            self.store.complete(analysis_id, output)
            if self.vector:
                self.vector.index_analysis(analysis_id, jira_key, output.model_dump_json())
            self.audit.write("analysis_completed", jira_key=jira_key, analysis_id=analysis_id)
            return output
        except Exception as error:
            self.store.fail(analysis_id, str(error))
            self.audit.write("analysis_failed", jira_key=jira_key, analysis_id=analysis_id, error=str(error))
            raise

    async def post_analysis(self, jira_key: str) -> str:
        record = self.store.latest(jira_key)
        if record is None or record.output is None:
            raise RuntimeError(f"No completed analysis exists for {jira_key}")
        if self.store.was_posted(record.analysis_id):
            raise RuntimeError(f"Analysis {record.analysis_id} was already posted")
        approval = input(f"Approve posting analysis {record.analysis_id} to {jira_key}? [y/N] ")
        if approval.strip().lower() != "y":
            raise RuntimeError("Posting not approved")
        self.store.mark_approved(record.analysis_id)
        body = record.output.model_dump_json(indent=2)
        comment_id = await JiraClient(self.settings).post_comment(jira_key, body)
        self.store.mark_posted(record.analysis_id, jira_key, comment_id)
        if self.vector:
            self.vector.index_analysis(
                record.analysis_id, jira_key, record.output.model_dump_json(), approved=True
            )
        self.audit.write("analysis_posted", jira_key=jira_key, analysis_id=record.analysis_id, comment_id=comment_id)
        return comment_id
