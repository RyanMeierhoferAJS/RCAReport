from db import client as db

_PRIORITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
_STATUS_ICON   = {"open": "○", "in_progress": "◐", "waiting": "⏳", "complete": "✓"}


def format_task_list(tasks: list[dict], numbered: bool = True) -> str:
    if not tasks:
        return "No open tasks."

    lines = ["*Open Tasks*\n"]
    for i, t in enumerate(tasks, 1):
        p    = _PRIORITY_ICON.get(t.get("priority", "medium"), "●")
        s    = _STATUS_ICON.get(t.get("status", "open"), "○")
        proj = f" \\[{t['project']}\\]" if t.get("project") else ""
        due  = f" _(due {t['due_date']})_" if t.get("due_date") else ""
        num  = f"{i}. " if numbered else ""
        lines.append(f"{num}{p} {s} {t['title']}{proj}{due}")

    if numbered:
        lines.append("\n_/done \\[number or title\\] to complete_")
    return "\n".join(lines)


def get_formatted_open_tasks() -> str:
    return format_task_list(db.get_open_tasks())
