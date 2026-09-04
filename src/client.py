"""A thin, deterministic client for the Usertour v2 REST API.

Only the endpoints this pipeline needs are wrapped. Every call raises
UsertourError with the response body on failure, and transient 429/5xx
responses are retried with a short backoff.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .config import Config

RETRY_STATUSES = {429, 500, 502, 503, 504}


class UsertourError(RuntimeError):
    """Raised for any non-successful API response."""


class UsertourClient:
    def __init__(self, config: Config, timeout: int = 30):
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
        )

    # -- low level ---------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
        retries: int = 3,
    ) -> Any:
        url = self._url(path)
        last_error: UsertourError | None = None
        for attempt in range(retries):
            resp = self.session.request(
                method, url, params=params, json=json, timeout=self.timeout
            )
            if resp.status_code in RETRY_STATUSES and attempt < retries - 1:
                last_error = self._error(resp)
                time.sleep(min(2 ** attempt, 8))
                continue
            if not resp.ok:
                raise self._error(resp)
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise last_error or UsertourError("Request failed after retries")

    @staticmethod
    def _error(resp: requests.Response) -> UsertourError:
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text
        return UsertourError(
            f"{resp.request.method} {resp.url} -> {resp.status_code}: {body}"
        )

    def _paginate(self, path: str, params: dict | None = None) -> list[dict]:
        params = dict(params or {})
        params.setdefault("limit", 100)
        results: list[dict] = []
        data = self._request("GET", path, params=params)
        while data:
            results.extend(data.get("results", []))
            next_url = data.get("next")
            if not next_url:
                break
            resp = self.session.get(next_url, timeout=self.timeout)
            if not resp.ok:
                raise self._error(resp)
            data = resp.json()
        return results

    # -- discovery ---------------------------------------------------------
    def me(self) -> dict:
        return self._request("GET", "/v2/me")

    def resolve_project_id(self) -> str:
        if self.config.project_id:
            return self.config.project_id
        projects = self.me().get("projects", [])
        if len(projects) == 1:
            return projects[0]["id"]
        ids = [p.get("id") for p in projects]
        raise UsertourError(
            f"Set USERTOUR_PROJECT_ID; the token can access {len(projects)} "
            f"projects: {ids}"
        )

    def list_themes(self, project_id: str) -> list[dict]:
        return self._paginate(f"/v2/projects/{project_id}/themes")

    def list_content(self, project_id: str, type: str | None = None) -> list[dict]:
        params = {"type": type} if type else None
        return self._paginate(f"/v2/projects/{project_id}/content", params=params)

    # -- authoring ---------------------------------------------------------
    def create_flow(self, project_id: str, name: str, theme_id: str) -> dict:
        return self._request(
            "POST",
            f"/v2/projects/{project_id}/content",
            json={"type": "flow", "name": name, "themeId": theme_id},
        )

    def update_version(
        self, project_id: str, content_id: str, version_id: str, payload: dict
    ) -> dict:
        return self._request(
            "PATCH",
            f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}",
            json=payload,
        )

    def validate_version(
        self, project_id: str, content_id: str, version_id: str
    ) -> dict:
        return self._request(
            "GET",
            f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}/validate",
        )

    def publish(
        self, project_id: str, content_id: str, version_id: str, environment_id: str
    ) -> dict:
        return self._request(
            "POST",
            f"/v2/projects/{project_id}/content/{content_id}/publish",
            json={"environmentId": environment_id, "versionId": version_id},
        )
