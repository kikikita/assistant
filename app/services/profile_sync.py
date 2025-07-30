from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.tomoru_team_api import TomoruTeamApiService
from app.schemas.tomoru_team import ExternalApiUpdateUserRequestDto, ExternalApiGetUserResponseDto
from app.db.session import SessionLocal
from app.crud.user import get_user_by_tg_id
from app.crud.resume import get_active_resume_for_user, get_or_create_active_resume

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Delayed export logic (→ external API)
# ---------------------------------------------------------------------------

_SYNC_DELAY = timedelta(minutes=30).total_seconds()
_pending_tasks: Dict[int, asyncio.Task] = {}

tomoru_api = TomoruTeamApiService()

def schedule_profile_export(user_tg_id: int) -> None:
    """Plan export of the local resume to external API in 30 minutes.

    Every time the user sends a new message, the timer is reset so that the
    export happens only after *30 minutes of inactivity*.
    """

    # We may be called from a sync context (FastAPI thread) or from async one.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from a worker thread (sync def endpoint).  Nothing we can do.
        logger.debug("Cannot schedule export: no running loop in current thread")
        return

    if user_tg_id in _pending_tasks:
        _pending_tasks[user_tg_id].cancel()

    _pending_tasks[user_tg_id] = loop.create_task(_delayed_export(user_tg_id))


async def _delayed_export(user_tg_id: int) -> None:
    try:
        await asyncio.sleep(_SYNC_DELAY)
        await _export_now(user_tg_id)
    except asyncio.CancelledError:
        pass
    finally:
        _pending_tasks.pop(user_tg_id, None)


async def _export_now(user_tg_id: int) -> None:
    db: Session = SessionLocal()
    try:
        user = get_user_by_tg_id(db, user_tg_id)
        if not user:
            return
        resume = get_active_resume_for_user(db, user.id)
        if not resume:
            return

        payload = _build_update_payload(resume.data)
        if not payload:
            return  # nothing to update

        await tomoru_api.update_user(user_telegram_id=user_tg_id, payload=payload)
        logger.info("Exported profile of user %s to Tomoru.Team", user_tg_id)
    except Exception:
        logger.exception("Failed to export profile of user %s", user_tg_id)
    finally:
        db.close()


def _build_update_payload(data: dict) -> ExternalApiUpdateUserRequestDto | None:
    # TODO: sync all fields
    mapping = {
        "first_name": "firstName",
        "last_name": "lastName",
        "work_status": "workStatus",
        "birthday": "birthday",
        "phone": "phone",
    }
    out: Dict[str, object] = {}
    for local_key, external_key in mapping.items():
        if val := data.get(local_key):
            out[external_key] = val
    if not out:
        return None
    return ExternalApiUpdateUserRequestDto(**out)

# ---------------------------------------------------------------------------
# Import logic (← external API)
# ---------------------------------------------------------------------------

async def import_profile_if_needed(user_tg_id: int) -> None:
    """Fetch profile from external API and merge into local resume/user."""
    db: Session = SessionLocal()
    try:
        try:
            external: ExternalApiGetUserResponseDto = await tomoru_api.get_user(user_tg_id)
        except Exception as e:
            logger.error("Failed to get profile of user %s: %s", user_tg_id, e)
            return

        user = get_user_by_tg_id(db, user_tg_id)
        if not user:
            return
        resume = get_or_create_active_resume(db, user.id)

        _merge_into_user(user, external)
        _merge_into_resume(resume.data, external)
        db.commit()
        logger.info("Imported profile of user %s from Tomoru.Team", user_tg_id)
    except Exception:
        logger.exception("Failed to import profile of user %s", user_tg_id)
    finally:
        db.close()


def _merge_into_user(user: User, ext: ExternalApiGetUserResponseDto):
    if ext.firstName is not None:
        user.first_name = ext.firstName
    if ext.lastName is not None:
        user.last_name = ext.lastName
    if ext.birthday is not None:
        user.birthday = ext.birthday
    if ext.phone is not None:
        user.phone = ext.phone


def _merge_into_resume(data: dict, ext: ExternalApiGetUserResponseDto):
    # TODO: sync all fields
    if ext.firstName is not None:
        data.setdefault("first_name", ext.firstName)
    if ext.lastName is not None:
        data.setdefault("last_name", ext.lastName)
    if ext.workStatus is not None:
        data.setdefault("work_status", ext.workStatus)
    if ext.birthday is not None:
        data.setdefault("birthday", str(ext.birthday))
    if ext.phone is not None:
        data.setdefault("phone", ext.phone)
