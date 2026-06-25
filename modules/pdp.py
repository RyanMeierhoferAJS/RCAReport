from db import client as db

_STATUS_EMOJI = {
    "not_started": "⬜",
    "in_progress":  "🔵",
    "on_track":     "🟢",
    "at_risk":      "🟡",
    "exceeded":     "⭐",
    "complete":     "✅",
}

_CAT_ORDER = ["leadership", "technical", "commercial", "personal", "general"]


def get_pdp_summary() -> str:
    actions = db.get_pdp_actions()
    if not actions:
        return (
            "*PDP Actions*\n\nNo actions set up yet.\n\n"
            "Add one: `/pdp add [title] | [category] | [objective]`"
        )

    by_cat: dict[str, list] = {}
    for a in actions:
        cat = a.get("category", "general")
        by_cat.setdefault(cat, []).append(a)

    parts = ["*PDP — Personal Development Plan*\n"]

    for cat in _CAT_ORDER:
        items = by_cat.get(cat, [])
        if not items:
            continue
        parts.append(f"*{cat.capitalize()}*")
        for a in items:
            emoji = _STATUS_EMOJI.get(a.get("status", "not_started"), "⬜")
            line = f"{emoji} {a['title']}"
            evidence = a.get("evidence") or []
            if evidence:
                line += f" ({len(evidence)} pieces of evidence)"
            parts.append(f"  {line}")
            if a.get("target_date"):
                parts.append(f"    _Due: {a['target_date']}_")

    exceeded = sum(1 for a in actions if a.get("status") == "exceeded")
    complete = sum(1 for a in actions if a.get("status") in ("exceeded", "complete"))
    parts.append(f"\n_{complete}/{len(actions)} complete — {exceeded} exceeded_")

    return "\n".join(parts)


def format_pdp_for_export(actions: list[dict]) -> str:
    if not actions:
        return "No PDP actions set up."
    lines = []
    for a in actions:
        emoji = _STATUS_EMOJI.get(a.get("status", "not_started"), "⬜")
        cat = a.get("category", "general").capitalize()
        line = f"{emoji} [{cat}] {a['title']} — Status: {a.get('status', 'not_started')}"
        evidence = a.get("evidence") or []
        if evidence:
            line += f"\n  Evidence ({len(evidence)}): " + "; ".join(evidence[-3:])
        lines.append(line)
    return "\n".join(lines)


def format_pdp_for_ai_analysis(actions: list[dict]) -> str:
    lines = []
    for a in actions:
        lines.append(f"ACTION: {a['title']}")
        lines.append(f"  Category: {a.get('category', 'general')}")
        lines.append(f"  Status: {a.get('status', 'not_started')}")
        if a.get("objective"):
            lines.append(f"  Objective: {a['objective']}")
        if a.get("target_date"):
            lines.append(f"  Target date: {a['target_date']}")
        evidence = a.get("evidence") or []
        if evidence:
            lines.append(f"  Evidence ({len(evidence)} items):")
            for e in evidence:
                lines.append(f"    - {e}")
        else:
            lines.append("  Evidence: none yet")
        lines.append("")
    return "\n".join(lines)
