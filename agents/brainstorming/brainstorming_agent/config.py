from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("BRAINSTORMING_MODEL", "openai:gpt-4.1-mini")
    jira_base_url: str | None = os.getenv("JIRA_BASE_URL")
    jira_email: str | None = os.getenv("JIRA_EMAIL")
    jira_api_token: str | None = os.getenv("JIRA_API_TOKEN")
    chroma_path: Path = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma"))
    sqlite_path: Path = Path(os.getenv("SQLITE_DATABASE_PATH", "./data/brainstorming.db"))
    log_path: Path = Path(os.getenv("AUDIT_LOG_DIRECTORY", "./data/logs"))
    max_concurrency: int = int(os.getenv("BRAINSTORMING_MAX_CONCURRENCY", "4"))
    max_retries: int = int(os.getenv("BRAINSTORMING_MAX_RETRIES", "3"))
    timeout_seconds: float = float(os.getenv("BRAINSTORMING_AGENT_TIMEOUT_SECONDS", "60"))

    def require_jira(self) -> None:
        if not all((self.jira_base_url, self.jira_email, self.jira_api_token)):
            raise RuntimeError("JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN are required")
