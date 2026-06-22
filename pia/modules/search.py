from db import client as db
from ai.router import answer_question


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


def search_and_answer(query: str) -> str:
    results = db.full_search(query)
    context = build_context_from_results(results)

    if not context:
        return "I couldn't find anything relevant to that in my memory yet."

    return answer_question(query, context)
