import logging
from telegram import Update
from telegram.ext import ContextTypes
from ai.router import extract_from_message
from modules.search import search_and_answer
from db import client as db

logger = logging.getLogger(__name__)

_QUESTION_STARTERS = (
    "what", "who", "when", "where", "how", "which", "why",
    "show", "list", "find", "tell", "have i", "did i",
)


def _looks_like_question(text: str) -> bool:
    lower = text.lower().strip()
    return lower.endswith("?") or lower.startswith(_QUESTION_STARTERS)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text       = update.message.text
    message_id = update.message.message_id
    chat_id    = update.message.chat_id

    capture_id = db.store_capture(
        raw_text=text,
        telegram_msg_id=message_id,
        telegram_chat_id=chat_id,
        media_type="text",
    )

    # Fast-path for obvious questions — skip Tier 1 extraction
    if _looks_like_question(text):
        result = search_and_answer(text)
        await update.message.reply_text(result, parse_mode="Markdown")
        return

    # Tier 1: classify and extract structured entities
    extracted = extract_from_message(text)

    # If AI also classified it as a question, answer it
    if extracted.get("classification") == "question":
        result = search_and_answer(text)
        await update.message.reply_text(result, parse_mode="Markdown")
        return

    stored = []

    for task in extracted.get("tasks", []):
        db.create_task(
            title=task["title"],
            description=task.get("description"),
            priority=task.get("priority", "medium"),
            due_date=task.get("due_date"),
            project=task.get("project"),
            source_capture_id=capture_id,
        )
        stored.append(f"✅ *Task:* {task['title']}")

    for decision in extracted.get("decisions", []):
        db.create_decision(
            title=decision["title"],
            description=decision.get("description"),
            reason=decision.get("reason"),
            alternatives=decision.get("alternatives", []),
            project=decision.get("project"),
            source_capture_id=capture_id,
        )
        stored.append(f"🎯 *Decision:* {decision['title']}")

    for achievement in extracted.get("achievements", []):
        db.create_career_event(
            type=achievement.get("type", "achievement"),
            title=achievement["title"],
            description=achievement.get("description"),
            value_pounds=achievement.get("value_pounds"),
            project=achievement.get("project"),
            source_capture_id=capture_id,
        )
        stored.append(f"🏆 *Achievement:* {achievement['title']}")

    for note in extracted.get("notes", []):
        db.create_note(
            content=note["content"],
            tags=note.get("tags", []),
            entities=note.get("entities", []),
            project=note.get("project"),
            source_capture_id=capture_id,
        )

    for idea in extracted.get("ideas", []):
        db.create_idea(
            title=idea["title"],
            description=idea.get("description"),
            category=idea.get("category", "general"),
            project=idea.get("project"),
            source_capture_id=capture_id,
        )
        stored.append(f"💡 *Idea:* {idea['title']}")

    for pdp_ev in extracted.get("pdp_evidence", []):
        action_title = pdp_ev.get("action_title", "")
        evidence_text = pdp_ev.get("evidence", "")
        exceeded = pdp_ev.get("exceeded", False)
        if action_title and evidence_text:
            actions = db.get_pdp_actions()
            matched = next(
                (a for a in actions if action_title.lower() in a["title"].lower()),
                None,
            )
            if matched:
                new_status = "exceeded" if exceeded else "in_progress"
                db.add_pdp_evidence(matched["id"], evidence_text, new_status)
                stored.append(f"📈 *PDP evidence logged* for: {matched['title']}")

    # Update last_activity on any mentioned projects
    for project in extracted.get("projects_mentioned", []):
        try:
            db.update_project_activity(project)
        except Exception:
            pass

    # Reply: use AI's natural response if available, else summarise what was stored
    reply = extracted.get("response", "")
    if not reply and stored:
        reply = "\n".join(stored)
    elif not reply:
        reply = "Got it, stored."

    await update.message.reply_text(reply, parse_mode="Markdown")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Placeholder — voice transcription (Whisper) coming in Phase 1.1
    await update.message.reply_text(
        "Voice notes are coming soon — send as text for now."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Something went wrong — please try again.")
