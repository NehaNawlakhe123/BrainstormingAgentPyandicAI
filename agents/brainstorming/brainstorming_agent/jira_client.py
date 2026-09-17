from __future__ import annotations

import base64
from datetime import datetime

import httpx

from .config import Settings
from .models import JiraEpic, JiraStory


class JiraClient:
    def __init__(self, settings: Settings):
        settings.require_jira()
        self.settings = settings
        credentials = f"{settings.jira_email}:{settings.jira_api_token}".encode()
        token = base64.b64encode(credentials).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict:
        url = f"{self.settings.jira_base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    async def get_epic_with_children(self, jira_key: str) -> JiraEpic:
        epic = await self._get(f"/rest/api/3/issue/{jira_key}")
        fields = epic["fields"]
        children = await self._get(
            "/rest/api/3/search",
            {"jql": f'"Epic Link" = {jira_key}', "maxResults": "100"},
        )
        return JiraEpic(
            epic_key=jira_key,
            summary=fields.get("summary", ""),
            description=str(fields.get("description") or ""),
            status=fields.get("status", {}).get("name", ""),
            priority=(fields.get("priority") or {}).get("name", ""),
            updated_at=datetime.fromisoformat(epic["fields"]["updated"].replace("Z", "+00:00")),
            children=[
                JiraStory(
                    story_key=item["key"],
                    summary=item["fields"].get("summary", ""),
                    description=str(item["fields"].get("description") or ""),
                    acceptance_criteria=str(item["fields"].get("customfield_10000") or ""),
                    status=(item["fields"].get("status") or {}).get("name", ""),
                    updated_at=datetime.fromisoformat(item["fields"]["updated"].replace("Z", "+00:00")),
                )
                for item in children.get("issues", [])
            ],
        )

    async def post_comment(self, jira_key: str, body: str) -> str:
        result = await self._post(f"/rest/api/3/issue/{jira_key}/comment", {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}})
        return str(result["id"])

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.settings.jira_base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            response.raise_for_status()
            return response.json()
