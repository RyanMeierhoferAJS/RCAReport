import logging
from db import client as db
from ai.router import answer_question

logger = logging.getLogger(__name__)


def build_context_from_results(results: dict[str, list[dict]]) -> str:
    parts = []

    if results.get("tasks"):
        parts.append("TASKS:\n" + "\n".join(
            f"- [{t['status'].upper()}] {t['title']}"
            + (f" (priority: {t['priority']})" if t.get("priority") else "")
            + (f" (due: {t['due_date']})" if t.get("due_date") else "")
            for t in results["tasks"]
        ))

    if results.get("decisions"):
        parts.append("DECISIONS:\n" + "\n".join(
            f"- {d['title']}"
            + (f" — {d['reason']}" if d.get("reason") else "")
            + (f" [{d.get('decided_at', '')[:10]}]")
            for d in results["decisions"]
        ))

    if results.get("career_events"):
        parts.append("CAREER/ACHIEVEMENTS:\n" + "\n".join(
            f"- [{e['type']}] {e['title']}"
            + (f" (£{e['value_pounds']:,.0f})" if e.get("value_pounds") else "")
            for e in results["career_events"]
        ))

    if results.get("notes"):
        parts.append("NOTES:\n" + "\n".join(
            f"- {n['content'][:300]}"
            for n in results["notes"]
        ))

    return "\n\n".join(parts)


def _fallback_context() -> str:
    """Pull all core data directly — used when semantic search returns nothing."""
    parts = []
    try:
        tasks = db.get_open_tasks()
        if tasks:
            parts.append("TASKS:\n" + "\n".join(
                f"- [{t.get('status','open').upper()}] {t['title']}"
                + (f" (priority: {t.get('priority','')})" if t.get("priority") else "")
                + (f" (due: {t['due_date']})" if t.get("due_date") else "")
                for t in tasks
            ))
    except Exception:
        pass

    try:
        decisions = db.get_recent_decisions(limit=20)
        if decisions:
            parts.append("DECISIONS:\n" + "\n".join(
                f"- {d['title']}" + (f" — {d['reason']}" if d.get("reason") else "")
                for d in decisions
            ))
    except Exception:
        pass

    return "\n\n".join(parts)


def search_and_answer(query: str) -> str:
    # Try semantic search first
    try:
        results = db.full_search(query)
        context = build_context_from_results(results)
    except Exception:
        logger.warning("Semantic search failed, falling back to direct query")
        context = ""

    # Fall back to direct DB query if semantic search returned nothing
    if not context:
        context = _fallback_context()

    if not context:
        return "I don't have any data stored yet. Try sending me some tasks or decisions first."

    return answer_question(query, context)
