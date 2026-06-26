from db import client as db


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def get_project_dashboard() -> str:
    summaries = db.get_project_summary()
    if not summaries:
        return "_No active projects with open tasks found._"

    lines = ["*Project Dashboard*\n"]
    for p in summaries:
        name      = p["name"]
        tasks     = p["tasks"]
        decisions = p["decisions"]

        high  = sum(1 for t in tasks if t.get("priority") == "high")
        total = len(tasks)

        header = f"*{name}* — {total} open task{'s' if total != 1 else ''}"
        if high:
            header += f" ({high} high priority)"
        lines.append(header)

        # Top 3 tasks by priority
        sorted_tasks = sorted(tasks, key=lambda t: _PRIORITY_ORDER.get(t.get("priority", "low"), 2))
        for t in sorted_tasks[:3]:
            pri = f"[{t['priority'].upper()}] " if t.get("priority") else ""
            lines.append(f"  • {pri}{t['title']}")
        if total > 3:
            lines.append(f"  _…{total - 3} more_")

        # Most recent decision
        if decisions:
            d = decisions[0]
            lines.append(f"  Last decision: _{d['title']}_")

        lines.append("")

    return "\n".join(lines).rstrip()
