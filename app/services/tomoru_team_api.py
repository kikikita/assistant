from __future__ import annotations

import logging

import httpx
from app.core.config import settings
from app.schemas.tomoru_team import (
    ExternalApiGetUserResponseDto,
    ExternalApiUpdateUserRequestDto,
)

logger = logging.getLogger(__name__)


class TomoruTeamApiService:
    """Thin asynchronous wrapper around Tomoru.Team mini-app backend."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.TOMORU_TEAM_API_URL.rstrip("/"),
            headers={
                "Authorization": f"Bearer {settings.TOMORU_TEAM_API_KEY.get_secret_value()}"
            },
            timeout=20.0,
        )
        logger.info(
            "Tomoru Team Service initialised with base URL %s",
            self._http.base_url,
        )

    # ---------------------------------------------------------------------
    # User profile
    # ---------------------------------------------------------------------

    async def get_user(self, user_telegram_id: int) -> ExternalApiGetUserResponseDto:
        """Fetch user profile by Telegram ID."""

        resp = await self._http.get(f"/external-api/user/{user_telegram_id}")
        resp.raise_for_status()
        return ExternalApiGetUserResponseDto(**resp.json())

    async def update_user(
        self,
        user_telegram_id: int,
        payload: ExternalApiUpdateUserRequestDto,
    ) -> None:
        """Patch user profile.  *payload* should contain only fields to update."""

        resp = await self._http.patch(
            f"/external-api/user/{user_telegram_id}",
            json=payload.model_dump(exclude_none=True),
        )
        resp.raise_for_status()

    
    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
