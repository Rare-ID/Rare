from __future__ import annotations

import httpx

from rare_sdk import AgentClient


class PlatformClient:
    def __init__(self, *, base_url: str, agent_client: AgentClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_client = agent_client
        self._http = httpx.Client()

    def close(self) -> None:
        self._http.close()

    def post(self, content: str) -> dict:
        signed = self.agent_client.sign_platform_action(
            action="post",
            action_payload={"content": content},
        )

        response = self._http.post(
            f"{self.base_url}/posts",
            json={
                "content": content,
                "nonce": signed["nonce"],
                "issued_at": signed["issued_at"],
                "expires_at": signed["expires_at"],
                "signature_by_session": signed["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {signed['session_token']}"},
        )
        response.raise_for_status()
        return response.json()

    def comment(self, post_id: str, content: str) -> dict:
        signed = self.agent_client.sign_platform_action(
            action="comment",
            action_payload={"post_id": post_id, "content": content},
        )

        response = self._http.post(
            f"{self.base_url}/comments",
            json={
                "post_id": post_id,
                "content": content,
                "nonce": signed["nonce"],
                "issued_at": signed["issued_at"],
                "expires_at": signed["expires_at"],
                "signature_by_session": signed["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {signed['session_token']}"},
        )
        response.raise_for_status()
        return response.json()
