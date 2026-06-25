import logging
from db import client as db
from ai.router import answer_question

logger = logging.getLogger(__name__)


def _base_context() -> str:
    """Always-present context: open tasks + recent decisions."""
    parts = []

    try:
        tasks = db.get_open_tasks()
        if tasks:
            parts.append("OPEN TASKS:\n" + "\n".join(
                f"- [{t.get('status', 'open').upper()}] {t['title']}"
                + (f" (priority: {t.get('priority', '')})" if t.get("priority") else "")
                + (f" (due: {t['due_date']})" if t.get("due_date") else "")
                + (f" [{t['project']}]" if t.get("project") else "")
                for t in tasks
            ))
    except Exception:
        logger.warning("Failed to load open tasks for context")

    try:
        decisions = db.get_recent_decisions(limit=15)
        if decisions:
            parts.append("RECENT DECISIONS:\n" + "\n".join(
                f"- {d['title']}"
                + (f" — {d['reason']}" if d.get("reason") else "")
                + (f" [{d.get('decided_at', '')[:10]}]")
                for d in decisions
            ))
    except Exception:
        logger.warning("Failed to load decisions for context")

    try:
        ideas = db.get_ideas(limit=30)
        if ideas:
            parts.append("IDEAS:\n" + "\n".join(
                f"- [{i.get('category', 'general')}] {i['title']}"
                + (f" — {i['description'][:150]}" if i.get("description") else "")
                + (f" ({i['status']})" if i.get("status") and i["status"] != "raw" else "")
                for i in ideas
            ))
    except Exception:
        logger.warning("Failed to load ideas for context")

    return "\n\n".join(parts)


def _semantic_context(query: str) -> str:
    """Additional context from semantic search — supplements base context."""
    try:
        results = db.full_search(query)
        parts = []

        # Only add career events and notes from semantic search
        # (tasks + decisions already covered by base context)
        if results.get("career_events"):
            parts.append("RELEVANT ACHIEVEMENTS:\n" + "\n".join(
                f"- [{e['type']}] {e['title']}"
                + (f" (£{e['value_pounds']:,.0f})" if e.get("value_pounds") else "")
                for e in results["career_events"]
            ))

        if results.get("notes"):
            parts.append("RELEVANT NOTES:\n" + "\n".join(
                f"- {n['content'][:300]}"
                for n in results["notes"]
            ))

        if results.get("ideas"):
            parts.append("RELEVANT IDEAS:\n" + "\n".join(
                f"- [{e.get('category', 'general')}] {e['title']}"
                + (f" — {e['description'][:200]}" if e.get("description") else "")
                for e in results["ideas"]
            ))

        return "\n\n".join(parts)
    except Exception:
        logger.warning("Semantic search failed, using base context only")
        return ""


def build_context_from_results(results: dict[str, list[dict]]) -> str:
    """Used by /think and /deep commands."""
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
            for d in results["decisions"]
        ))

    if results.get("career_events"):
        parts.append("ACHIEVEMENTS:\n" + "\n".join(
            f"- [{e['type']}] {e['title']}"
            + (f" (£{e['value_pounds']:,.0f})" if e.get("value_pounds") else "")
            for e in results["career_events"]
        ))

    if results.get("notes"):
        parts.append("NOTES:\n" + "\n".join(
            f"- {n['content'][:300]}"
            for n in results["notes"]
        ))

    if results.get("ideas"):
        parts.append("IDEAS:\n" + "\n".join(
            f"- [{e.get('category', 'general')}] {e['title']}"
            + (f" — {e['description'][:200]}" if e.get("description") else "")
            for e in results["ideas"]
        ))

    return "\n\n".join(parts)


def search_and_answer(query: str) -> str:
    base = _base_context()
    semantic = _semantic_context(query)

    context = "\n\n".join(filter(None, [base, semantic]))

    if not context:
        return "I don't have any data stored yet. Try sending me some tasks or decisions first."

    return answer_question(query, context)
