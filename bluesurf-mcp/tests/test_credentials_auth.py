from __future__ import annotations

import httpx
import pytest

from bluesurf_client.auth.credentials import CredentialsAuth
from bluesurf_client.constants import IDENTITY_COOKIE, LOGIN_PATH


@pytest.mark.asyncio
async def test_apply_with_cached_cookie_skips_post() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    async with httpx.AsyncClient(
        base_url="https://surf.test", transport=transport
    ) as client:
        auth = CredentialsAuth("alice", "pw", initial_session_cookie="cached")
        await auth.apply(client)
        assert client.cookies.get(IDENTITY_COOKIE) == "cached"


@pytest.mark.asyncio
async def test_refresh_posts_and_persists() -> None:
    persisted: list[tuple[str, str]] = []

    def persist(u: str, c: str) -> None:
        persisted.append((u, c))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == LOGIN_PATH
        return httpx.Response(
            200,
            headers={"set-cookie": f"{IDENTITY_COOKIE}=newval; Path=/; HttpOnly"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://surf.test", transport=transport
    ) as client:
        auth = CredentialsAuth(
            "alice",
            "pw",
            initial_session_cookie="old",
            persist_session=True,
            persist_cookie=persist,
        )
        await auth.refresh(client)
        assert client.cookies.get(IDENTITY_COOKIE) == "newval"
        assert persisted == [("alice", "newval")]
