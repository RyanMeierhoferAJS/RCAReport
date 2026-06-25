from db import client as db

_STATUS_EMOJI = {
    "raw":     "💡",
    "refined": "🔧",
    "parked":  "⏸",
    "shipped": "✅",
}

_CAT_LABEL = {
    "product":  "Product",
    "process":  "Process",
    "research": "Research",
    "personal": "Personal",
    "general":  "General",
}


def get_formatted_ideas(status: str | None = None) -> str:
    ideas = db.get_ideas(status=status)
    if not ideas:
        msg = "No ideas" + (f" with status '{status}'" if status else "") + " yet."
        return msg

    by_status: dict[str, list] = {}
    for idea in ideas:
        s = idea.get("status", "raw")
        by_status.setdefault(s, []).append(idea)

    parts = ["*Ideas*\n"]
    for s in ["raw", "refined", "parked", "shipped"]:
        items = by_status.get(s, [])
        if not items:
            continue
        emoji = _STATUS_EMOJI.get(s, "•")
        parts.append(f"{emoji} *{s.capitalize()}*")
        for idea in items:
            cat = _CAT_LABEL.get(idea.get("category", "general"), "")
            line = f"  • {idea['title']}"
            if cat and cat != "General":
                line += f" [{cat}]"
            if idea.get("project"):
                line += f" ({idea['project']})"
            parts.append(line)
            if idea.get("description"):
                parts.append(f"    _{idea['description'][:120]}_")

    return "\n".join(parts)


def format_ideas_for_export(ideas: list[dict]) -> str:
    if not ideas:
        return "No ideas captured yet."
    lines = []
    for idea in ideas:
        emoji = _STATUS_EMOJI.get(idea.get("status", "raw"), "💡")
        cat = _CAT_LABEL.get(idea.get("category", "general"), "General")
        line = f"{emoji} [{cat}] {idea['title']}"
        if idea.get("description"):
            line += f" — {idea['description'][:200]}"
        if idea.get("project"):
            line += f" ({idea['project']})"
        lines.append(line)
    return "\n".join(lines)
