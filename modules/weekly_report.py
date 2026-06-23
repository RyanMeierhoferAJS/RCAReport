from datetime import date, timedelta
from db import client as db
from ai.router import generate_weekly_report


def _build_context() -> str:
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    tasks    = db.get_open_tasks()
    decisions = db.get_recent_decisions(limit=30)
    projects = db.get_active_projects()
    career   = db.get_career_events(year=date.today().year, limit=100)

    recent_decisions = [d for d in decisions if d.get("decided_at", "")[:10] >= week_ago]
    recent_career    = [e for e in career if e.get("created_at", "")[:10] >= week_ago]

    parts = []

    parts.append("ALL OPEN TASKS:\n" + "\n".join(
        f"[{t.get('priority', 'medium').upper()}] [{t.get('status', 'open')}] {t['title']}"
        + (f" (due {t['due_date']})" if t.get("due_date") else "")
        for t in tasks[:25]
    ))

    if recent_decisions:
        parts.append("DECISIONS THIS WEEK:\n" + "\n".join(
            f"- {d['title']}" + (f": {d['reason']}" if d.get("reason") else "")
            for d in recent_decisions
        ))

    if recent_career:
        parts.append("ACHIEVEMENTS THIS WEEK:\n" + "\n".join(
            f"- [{e['type']}] {e['title']}"
            + (f" (£{e['value_pounds']:,.0f})" if e.get("value_pounds") else "")
            for e in recent_career
        ))

    parts.append("ACTIVE PROJECTS:\n" + "\n".join(
        f"- {p['name']} ({p['status']}): {p.get('next_milestone', 'no milestone set')}"
        for p in projects
    ))

    return "\n\n".join(parts)


def get_weekly_report() -> str:
    context = _build_context()
    report  = generate_weekly_report(context)
    db.store_weekly_report(report, date.today())
    return report
