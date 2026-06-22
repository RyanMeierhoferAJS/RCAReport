from db import client as db


def format_decision_list(decisions: list[dict]) -> str:
    if not decisions:
        return "No decisions recorded yet."

    lines = ["*Recent Decisions*\n"]
    for d in decisions:
        date_str = d.get("decided_at", "")[:10]
        proj = f" \\[{d['project']}\\]" if d.get("project") else ""
        lines.append(f"• *{d['title']}*{proj} _{date_str}_")
        if d.get("reason"):
            lines.append(f"  ↳ {d['reason']}")

    return "\n".join(lines)


def get_formatted_decisions(limit: int = 10) -> str:
    return format_decision_list(db.get_recent_decisions(limit=limit))
