"""GitHub skill source — searches for SKILL.md in public repos."""

from __future__ import annotations

import structlog

from opensquilla.env import trust_env as _trust_env
from opensquilla.skills.hub.source import SkillBundle, SkillMeta, SkillSource

log = structlog.get_logger(__name__)


class GitHubSource(SkillSource):
    """Skill source backed by GitHub code search."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @property
    def source_id(self) -> str:
        return "github"

    @property
    def trust_level(self) -> str:
        return "community"

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            h["Authorization"] = f"token {self._token}"
        return h

    async def search(self, query: str, limit: int = 20) -> list[SkillMeta]:
        import httpx

        search_query = f"{query} filename:SKILL.md"
        url = "https://api.github.com/search/code"
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=_trust_env()) as client:
                resp = await client.get(
                    url,
                    params={"q": search_query, "per_page": min(limit, 30)},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("github.search_failed", error=str(exc))
            return []

        results = []
        for item in data.get("items", []):
            repo = item.get("repository", {})
            full_name = repo.get("full_name", "")
            path = item.get("path", "")
            # Extract skill name from path (e.g. "skills/apple-notes/SKILL.md" → "apple-notes")
            parts = path.rsplit("/", 2)
            skill_name = parts[-2] if len(parts) >= 2 else full_name

            results.append(
                SkillMeta(
                    name=skill_name,
                    description=repo.get("description", ""),
                    source_id=self.source_id,
                    trust_level=self.trust_level,
                    identifier=f"{full_name}:{path}",
                    homepage=repo.get("html_url", ""),
                )
            )
        return results[:limit]

    async def fetch(self, identifier: str) -> SkillBundle | None:
        import httpx

        # identifier format: "owner/repo:path/to/SKILL.md"
        if ":" not in identifier:
            return None
        repo_full, file_path = identifier.split(":", 1)
        skill_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""

        try:
            async with httpx.AsyncClient(timeout=15, trust_env=_trust_env()) as client:
                # Fetch SKILL.md
                url = f"https://raw.githubusercontent.com/{repo_full}/HEAD/{file_path}"
                resp = await client.get(url, headers=self._headers())
                resp.raise_for_status()
                skill_md = resp.text
        except Exception as exc:
            log.warning("github.fetch_failed", identifier=identifier, error=str(exc))
            return None

        name = skill_dir.rsplit("/", 1)[-1] if skill_dir else repo_full.split("/")[-1]
        return SkillBundle(name=name, files={"SKILL.md": skill_md})

    async def inspect(self, identifier: str) -> SkillMeta | None:
        if ":" not in identifier:
            return None
        repo_full, file_path = identifier.split(":", 1)
        parts = file_path.rsplit("/", 2)
        skill_name = parts[-2] if len(parts) >= 2 else repo_full.split("/")[-1]
        return SkillMeta(
            name=skill_name,
            source_id=self.source_id,
            trust_level=self.trust_level,
            identifier=identifier,
            homepage=f"https://github.com/{repo_full}",
        )
