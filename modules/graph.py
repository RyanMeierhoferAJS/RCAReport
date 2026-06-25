"""
Microsoft Graph API client — AJS Outlook calendar + email.
Uses client credentials flow (app-only, no user sign-in required).
"""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from config import (
    GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET,
    GRAPH_USER_EMAIL, TIMEZONE,
)

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TIMEZONE)

_TOKEN_URL   = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_BASE  = "https://graph.microsoft.com/v1.0"
_SCOPE       = "https://graph.microsoft.com/.default"

_token_cache: dict = {}


def _is_configured() -> bool:
    return all([GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_USER_EMAIL])


def _get_token() -> str | None:
    if not _is_configured():
        return None
    now = datetime.utcnow().timestamp()
    if _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]
    try:
        resp = requests.post(
            _TOKEN_URL.format(tenant=GRAPH_TENANT_ID),
            data={
                "grant_type":    "client_credentials",
                "client_id":     GRAPH_CLIENT_ID,
                "client_secret": GRAPH_CLIENT_SECRET,
                "scope":         _SCOPE,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 3600)
        return _token_cache["token"]
    except Exception:
        logger.error("Graph token fetch failed", exc_info=True)
        return None


def _get(path: str, params: dict | None = None) -> dict | None:
    token = _get_token()
    if not token:
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

    start = datetime(target_date.year, target_date.month, target_date.day,
                     0, 0, 0, tzinfo=_TZ)
    end   = start + timedelta(days=1)

    data = _get(
        f"/users/{GRAPH_USER_EMAIL}/calendarView",
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

        start_local = datetime.fromisoformat(start_raw).replace(tzinfo=_TZ) if "+" not in start_raw and "Z" not in start_raw \
                      else datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(_TZ)
        end_local   = datetime.fromisoformat(end_raw).replace(tzinfo=_TZ) if "+" not in end_raw and "Z" not in end_raw \
                      else datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(_TZ)

        location = (item.get("location") or {}).get("displayName", "").strip()
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
        f"/users/{GRAPH_USER_EMAIL}/messages",
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
