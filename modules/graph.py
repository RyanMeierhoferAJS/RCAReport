"""
Microsoft Graph API client — AJS Outlook calendar + email.
Uses device code flow (delegated permissions, no admin consent needed).
One-time browser login via /connect; refresh token stored in Supabase.
"""
import asyncio
import logging
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from config import (
    GRAPH_TENANT_ID, GRAPH_CLIENT_ID,
    TIMEZONE, TELEGRAM_ALLOWED_USER_ID,
)

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TIMEZONE)

_TOKEN_URL  = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_DEVICE_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode"
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_SCOPES     = "Calendars.ReadWrite Mail.ReadWrite Mail.Send OnlineMeetings.ReadWrite offline_access"

_mem_token: dict = {}  # in-process cache


def _is_configured() -> bool:
    return bool(GRAPH_TENANT_ID and GRAPH_CLIENT_ID)


def _load_db_token() -> dict | None:
    try:
        from db import client as db
        return db.get_oauth_token("graph")
    except Exception:
        return None


def _persist_token(access_token: str, refresh_token: str, expires_in: int) -> None:
    try:
        from db import client as db
        db.save_oauth_token(
            key="graph",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(time.time()) + expires_in,
        )
    except Exception:
        logger.error("Failed to persist Graph token", exc_info=True)


def _refresh(refresh_token: str) -> dict | None:
    try:
        resp = requests.post(
            _TOKEN_URL.format(tenant=GRAPH_TENANT_ID),
            data={
                "grant_type":    "refresh_token",
                "client_id":     GRAPH_CLIENT_ID,
                "refresh_token": refresh_token,
                "scope":         _SCOPES,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.error("Graph token refresh failed", exc_info=True)
        return None


def _get_token() -> str | None:
    if not _is_configured():
        return None

    now = time.time()

    if _mem_token.get("expires_at", 0) > now + 60:
        return _mem_token["access_token"]

    stored = _load_db_token()
    if not stored:
        return None

    if stored["expires_at"] > now + 60:
        _mem_token.update(stored)
        return stored["access_token"]

    if not stored.get("refresh_token"):
        return None

    data = _refresh(stored["refresh_token"])
    if not data or "access_token" not in data:
        return None

    new_rt = data.get("refresh_token") or stored["refresh_token"]
    _persist_token(data["access_token"], new_rt, data.get("expires_in", 3600))
    _mem_token["access_token"] = data["access_token"]
    _mem_token["expires_at"]   = now + data.get("expires_in", 3600)
    return data["access_token"]


# ── Device code flow ──────────────────────────────────────────────────────────

def start_device_code_flow() -> dict:
    """Returns the /devicecode response (user_code, verification_uri, device_code, interval, expires_in)."""
    resp = requests.post(
        _DEVICE_URL.format(tenant=GRAPH_TENANT_ID),
        data={"client_id": GRAPH_CLIENT_ID, "scope": _SCOPES},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _poll_once(device_code: str) -> dict | str | None:
    """Returns token dict on success, 'pending'/'slow_down' strings, or None on error."""
    try:
        resp = requests.post(
            _TOKEN_URL.format(tenant=GRAPH_TENANT_ID),
            data={
                "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
                "client_id":   GRAPH_CLIENT_ID,
                "device_code": device_code,
            },
            timeout=15,
        )
        data = resp.json()
        err = data.get("error")
        if err == "authorization_pending":
            return "pending"
        if err == "slow_down":
            return "slow_down"
        if err:
            logger.warning("Device code error: %s", data.get("error_description", err))
            return None
        return data
    except Exception:
        logger.error("Device code poll request failed", exc_info=True)
        return None


async def run_device_code_polling(app, device_code: str, interval: int, expires_in: int) -> None:
    """Background async task started by /connect to poll until the user logs in."""
    deadline = time.time() + expires_in
    while time.time() < deadline:
        await asyncio.sleep(interval)
        result = _poll_once(device_code)
        if result == "pending":
            continue
        if result == "slow_down":
            interval = min(interval + 5, 30)
            continue
        if isinstance(result, dict) and "access_token" in result:
            rt = result.get("refresh_token", "")
            _persist_token(result["access_token"], rt, result.get("expires_in", 3600))
            _mem_token["access_token"] = result["access_token"]
            _mem_token["expires_at"]   = time.time() + result.get("expires_in", 3600)
            await app.bot.send_message(
                chat_id=TELEGRAM_ALLOWED_USER_ID,
                text="✅ *Microsoft Graph connected!* Calendar and email access is now active.",
                parse_mode="Markdown",
            )
            return
        await app.bot.send_message(
            chat_id=TELEGRAM_ALLOWED_USER_ID,
            text="❌ Graph connection failed. Try `/connect` again.",
            parse_mode="Markdown",
        )
        return

    await app.bot.send_message(
        chat_id=TELEGRAM_ALLOWED_USER_ID,
        text="⏱ Login code expired before you signed in. Try `/connect` again.",
        parse_mode="Markdown",
    )


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | None:
    token = _get_token()
    if not token:
        logger.warning("Graph: no valid token — use /connect to authenticate")
        return None
    try:
        resp = requests.get(
            f"{_GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.error("Graph GET %s failed", path, exc_info=True)
        return None


# ── Calendar ──────────────────────────────────────────────────────────────────

def get_calendar_events(target_date: date) -> list[dict]:
    if not _is_configured():
        return []

    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=_TZ)
    end   = start + timedelta(days=1)

    data = _get(
        "/me/calendarView",
        params={
            "startDateTime": start.isoformat(),
            "endDateTime":   end.isoformat(),
            "$select":       "subject,start,end,location,isAllDay,onlineMeeting,bodyPreview",
            "$orderby":      "start/dateTime",
            "$top":          "50",
        },
    )
    if not data:
        return []

    events = []
    for item in data.get("value", []):
        is_allday = item.get("isAllDay", False)
        start_raw = item["start"]["dateTime"]
        end_raw   = item["end"]["dateTime"]

        def _parse(raw: str) -> datetime:
            if "+" in raw or raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(_TZ)
            return datetime.fromisoformat(raw).replace(tzinfo=_TZ)

        start_local = _parse(start_raw)
        end_local   = _parse(end_raw)

        location  = (item.get("location") or {}).get("displayName", "").strip()
        teams_url = (item.get("onlineMeeting") or {}).get("joinUrl", "")

        events.append({
            "start_time": "All day" if is_allday else start_local.strftime("%H:%M"),
            "end_time":   "" if is_allday else end_local.strftime("%H:%M"),
            "title":      item.get("subject", "Untitled"),
            "location":   location[:80] if location else "",
            "teams_url":  teams_url,
            "label":      "AJS",
            "_sort":      start_local,
        })

    return events


# ── Email ─────────────────────────────────────────────────────────────────────

def get_recent_emails(hours: int = 1) -> list[dict]:
    """Fetch emails received in the last `hours` hours."""
    if not _is_configured():
        return []

    since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = _get(
        "/me/messages",
        params={
            "$filter":  f"receivedDateTime ge {since} and isDraft eq false",
            "$select":  "subject,from,receivedDateTime,bodyPreview,body",
            "$orderby": "receivedDateTime desc",
            "$top":     "20",
        },
    )
    if not data:
        return []

    emails = []
    for item in data.get("value", []):
        sender = (item.get("from") or {}).get("emailAddress", {})
        emails.append({
            "subject":   item.get("subject", "(no subject)"),
            "from_name": sender.get("name", ""),
            "from_addr": sender.get("address", ""),
            "received":  item.get("receivedDateTime", ""),
            "preview":   item.get("bodyPreview", "")[:500],
            "body":      (item.get("body") or {}).get("content", "")[:3000],
        })

    return emails


def format_email_for_extraction(email: dict) -> str:
    return (
        f"From: {email['from_name']} <{email['from_addr']}>\n"
        f"Subject: {email['subject']}\n"
        f"Received: {email['received']}\n\n"
        f"{email['preview']}"
    )
