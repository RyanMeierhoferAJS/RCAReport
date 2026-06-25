import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

from config import CALENDAR_FEEDS, TIMEZONE

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TIMEZONE)


def _to_local(dt_value) -> datetime | None:
    if isinstance(dt_value, datetime):
        return dt_value.replace(tzinfo=_TZ) if dt_value.tzinfo is None else dt_value.astimezone(_TZ)
    if isinstance(dt_value, date):
        return datetime(dt_value.year, dt_value.month, dt_value.day, tzinfo=_TZ)
    return None


def _fetch(label: str, url: str, target_date: date) -> list[dict]:
    if not url:
        return []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)

        events = []
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            dtstart = component.get("DTSTART")
            if not dtstart:
                continue
            start_local = _to_local(dtstart.dt)
            if not start_local or start_local.date() != target_date:
                continue

            dtend = component.get("DTEND")
            end_local = _to_local(dtend.dt) if dtend else None
            is_allday = isinstance(dtstart.dt, date) and not isinstance(dtstart.dt, datetime)

            events.append({
                "start_time": "All day" if is_allday else start_local.strftime("%H:%M"),
                "end_time":   "" if is_allday or not end_local else end_local.strftime("%H:%M"),
                "title":      str(component.get("SUMMARY", "Untitled")),
                "location":   str(component.get("LOCATION", "")).strip()[:80],
                "label":      label,
                "_sort":      start_local,
            })

        return events
    except Exception:
        logger.warning("Calendar feed [%s] failed", label, exc_info=True)
        return []


def _get_events(target_date: date) -> list[dict]:
    events = []

    # Microsoft Graph (AJS Outlook)
    try:
        from modules.graph import get_calendar_events
        events.extend(get_calendar_events(target_date))
    except Exception:
        logger.warning("Graph calendar fetch failed", exc_info=True)

    # iCal feeds (ASR, Home/Google)
    for label, url in CALENDAR_FEEDS:
        events.extend(_fetch(label, url, target_date))

    events.sort(key=lambda e: e["_sort"])
    return events


def get_today_events() -> list[dict]:
    return _get_events(date.today())


def get_tomorrow_events() -> list[dict]:
    return _get_events(date.today() + timedelta(days=1))


def format_events(events: list[dict]) -> str:
    if not events:
        return "No meetings."
    lines = []
    for e in events:
        time_str = e["start_time"] + (f"–{e['end_time']}" if e["end_time"] else "")
        label    = f" \[{e['label']}\]" if e["label"] else ""
        loc      = f"\n  📍 _{e['location']}_" if e["location"] else ""
        lines.append(f"• {time_str} *{e['title']}*{label}{loc}")
    return "\n".join(lines)


def format_events_for_context(events: list[dict]) -> str:
    """Plain text for AI digest context."""
    if not events:
        return "No meetings today."
    lines = []
    for e in events:
        time_str = e["start_time"] + (f"-{e['end_time']}" if e["end_time"] else "")
        loc      = f" @ {e['location']}" if e["location"] else ""
        lines.append(f"  {time_str} [{e['label']}] {e['title']}{loc}")
    return "\n".join(lines)
