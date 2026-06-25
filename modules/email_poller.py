"""
Polls AJS Outlook for new emails via Graph API, extracts tasks/decisions,
and forwards actionable emails to Telegram.
"""
import logging
from datetime import datetime, timezone

from modules.graph import get_recent_emails, format_email_for_extraction
from ai.router import extract_from_message
from db import client as db

logger = logging.getLogger(__name__)

# Track last-processed email timestamp to avoid duplicates
_last_checked: datetime | None = None


def _should_skip(email: dict) -> bool:
    """Skip newsletters, automated notifications, no-reply senders."""
    addr = email.get("from_addr", "").lower()
    subj = email.get("subject", "").lower()
    skip_senders = ("noreply", "no-reply", "donotreply", "notifications@", "mailer@",
                    "newsletter", "alert@", "support@", "info@")
    skip_subjects = ("unsubscribe", "newsletter", "out of office", "automatic reply",
                     "delivery failed", "read receipt")
    return (
        any(s in addr for s in skip_senders) or
        any(s in subj for s in skip_subjects)
    )


def poll_emails(app) -> list[str]:
    """
    Check for new emails, extract entities, return list of Telegram messages to send.
    Called by the scheduler every 15 minutes.
    """
    global _last_checked
    messages = []

    try:
        emails = get_recent_emails(hours=1)
        if not emails:
            return []

        now = datetime.now(timezone.utc)
        cutoff = _last_checked or now

        new_emails = []
        for email in emails:
            try:
                received = datetime.fromisoformat(
                    email["received"].replace("Z", "+00:00")
                )
                if received > cutoff:
                    new_emails.append(email)
            except Exception:
                continue

        _last_checked = now

        for email in new_emails:
            if _should_skip(email):
                logger.info("Skipping email: %s", email["subject"])
                continue

            text = format_email_for_extraction(email)
            extracted = extract_from_message(text)

            stored = []

            for task in extracted.get("tasks", []):
                db.create_task(
                    title=task["title"],
                    description=task.get("description"),
                    priority=task.get("priority", "medium"),
                    due_date=task.get("due_date"),
                    project=task.get("project"),
                )
                stored.append(f"✅ *Task:* {task['title']}")

            for decision in extracted.get("decisions", []):
                db.create_decision(
                    title=decision["title"],
                    description=decision.get("description"),
                    reason=decision.get("reason"),
                    alternatives=decision.get("alternatives", []),
                    project=decision.get("project"),
                )
                stored.append(f"🎯 *Decision:* {decision['title']}")

            for idea in extracted.get("ideas", []):
                db.create_idea(
                    title=idea["title"],
                    description=idea.get("description"),
                    category=idea.get("category", "general"),
                    project=idea.get("project"),
                )
                stored.append(f"💡 *Idea:* {idea['title']}")

            if stored:
                header = f"📧 *Email from {email['from_name']}*\n_{email['subject']}_\n\n"
                messages.append(header + "\n".join(stored))

    except Exception:
        logger.exception("Email poll failed")

    return messages
