from datetime import date
from db import client as db
from ai.router import generate_digest


def _build_context() -> str:
    tasks    = db.get_open_tasks()
    projects = db.get_active_projects()
    parts    = []

    if tasks:
        waiting = [t for t in tasks if t.get("status") == "waiting"]
        parts.append("OPEN TASKS:\n" + "\n".join(
            f"[{t.get('priority', 'medium').upper()}] [{t.get('status', 'open')}] {t['title']}"
            + (f" (due {t['due_date']})" if t.get("due_date") else "")
            for t in tasks[:20]
        ))
        if waiting:
            parts.append("WAITING FOR:\n" + "\n".join(
                f"- {t['title']}" for t in waiting
            ))

    if projects:
        parts.append("ACTIVE PROJECTS:\n" + "\n".join(
            f"- {p['name']}: {p.get('next_milestone', 'no milestone set')}"
            for p in projects
        ))

    return "\n\n".join(parts)


def get_daily_digest() -> str:
    context = _build_context()
    digest  = generate_digest(context)
    db.store_daily_digest(digest, date.today())
    return digest
