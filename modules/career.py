from datetime import date
from db import client as db

_TYPE_ICON = {
    "achievement":              "🏆",
    "cost_avoidance":           "💰",
    "reliability_improvement":  "⚙️",
    "qualification":            "📜",
    "training_delivered":       "🎓",
    "presentation":             "📊",
    "project_win":              "🎯",
    "other":                    "📝",
}


def format_career_events(events: list[dict]) -> str:
    if not events:
        return "No career events recorded."

    lines = []
    for e in events:
        icon  = _TYPE_ICON.get(e.get("type", "other"), "📝")
        proj  = f" \\[{e['project']}\\]" if e.get("project") else ""
        value = f" _(£{e['value_pounds']:,.0f})_" if e.get("value_pounds") else ""
        lines.append(f"{icon} *{e['title']}*{proj}{value}")
        if e.get("description"):
            lines.append(f"  {e['description']}")

    return "\n".join(lines)


def get_career_summary(year: int | None = None) -> str:
    yr = year or date.today().year
    events = db.get_career_events(year=yr)

    if not events:
        return f"No career events recorded for {yr}."

    total_value = sum(e.get("value_pounds") or 0 for e in events)
    header = f"*Career Journal {yr}* — {len(events)} events"
    if total_value:
        header += f", £{total_value:,.0f} total value"

    return header + "\n\n" + format_career_events(events)
