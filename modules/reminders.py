from datetime import date
from db import client as db


def get_due_reminder() -> str | None:
    """
    Returns a Telegram message if there are overdue or due-today tasks, else None.
    """
    due = db.get_due_tasks()
    overdue   = due["overdue"]
    due_today = due["due_today"]

    if not overdue and not due_today:
        return None

    lines = ["*Midday check-in*\n"]

    if overdue:
        lines.append(f"*⚠️ Overdue ({len(overdue)})*")
        for t in overdue[:5]:
            days_late = (date.today() - date.fromisoformat(t["due_date"])).days
            proj = f" ({t['project']})" if t.get("project") else ""
            lines.append(f"• {t['title']}{proj} — {days_late}d late")
        if len(overdue) > 5:
            lines.append(f"  _…and {len(overdue) - 5} more_")

    if due_today:
        lines.append(f"\n*📅 Due today ({len(due_today)})*")
        for t in due_today[:5]:
            proj = f" ({t['project']})" if t.get("project") else ""
            pri  = f"[{t['priority'].upper()}] " if t.get("priority") else ""
            lines.append(f"• {pri}{t['title']}{proj}")

    lines.append("\nUse /done to clear completed items.")
    return "\n".join(lines)
