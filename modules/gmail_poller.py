"""
Gmail IMAP poller — reads recent emails, extracts tasks/decisions/ideas.
Uses an app password (no OAuth). Setup: Google Account → Security →
2-Step Verification → App passwords → create one for PIA.
"""
import email
import imaplib
import logging
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

from ai.router import extract_from_message
from db import client as db

logger = logging.getLogger(__name__)

_IMAP_HOST   = "imap.gmail.com"
_SKIP_SENDERS  = ("noreply", "no-reply", "donotreply", "notifications@", "mailer@",
                   "newsletter", "alert@", "support@", "info@")
_SKIP_SUBJECTS = ("unsubscribe", "newsletter", "out of office", "automatic reply",
                  "delivery failed", "read receipt")

_last_checked: datetime | None = None


def _is_configured() -> bool:
    from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD
    return bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD)


def _should_skip(from_addr: str, subject: str) -> bool:
    addr = from_addr.lower()
    subj = subject.lower()
    return (
        any(s in addr for s in _SKIP_SENDERS) or
        any(s in subj for s in _SKIP_SUBJECTS)
    )


def _decode_str(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            result.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(chunk)
    return "".join(result)


def _get_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ct  = part.get_content_type()
            cd  = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    pass
        return ""
    charset = msg.get_content_charset() or "utf-8"
    try:
        return msg.get_payload(decode=True).decode(charset, errors="replace")
    except Exception:
        return ""


def poll_gmail() -> list[str]:
    """
    Fetch unprocessed Gmail messages, extract entities, return Telegram messages.
    Called every 15 minutes by the scheduler.
    """
    global _last_checked
    if not _is_configured():
        return []

    from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD

    messages = []
    now = datetime.now(timezone.utc)
    cutoff = _last_checked or (now - timedelta(hours=1))

    try:
        mail = imaplib.IMAP4_SSL(_IMAP_HOST)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX", readonly=True)

        # IMAP SINCE is day-granular; we filter precisely by timestamp below
        since_str = cutoff.strftime("%d-%b-%Y")
        status, data = mail.search(None, f'SINCE "{since_str}"')
        if status != "OK" or not data[0]:
            mail.logout()
            _last_checked = now
            return []

        uids = data[0].split()
        for uid in reversed(uids[-20:]):  # newest first, cap at 20
            try:
                status, raw = mail.fetch(uid, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(raw[0][1])

                date_str = msg.get("Date", "")
                try:
                    received = parsedate_to_datetime(date_str)
                    if received.tzinfo is None:
                        received = received.replace(tzinfo=timezone.utc)
                    if received <= cutoff:
                        continue
                except Exception:
                    continue

                from_raw  = msg.get("From", "")
                from_name, from_addr = parseaddr(from_raw)
                from_name = _decode_str(from_name) or from_addr
                subject   = _decode_str(msg.get("Subject", "(no subject)"))
                body      = _get_body(msg)

                if _should_skip(from_addr, subject):
                    logger.info("Gmail: skipping %s", subject)
                    continue

                text = (
                    f"From: {from_name} <{from_addr}>\n"
                    f"Subject: {subject}\n"
                    f"Received: {received.isoformat()}\n\n"
                    f"{body[:2000]}"
                )
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
                    header = f"📧 *Email from {from_name}*\n_{subject}_\n\n"
                    messages.append(header + "\n".join(stored))

            except Exception:
                logger.warning("Gmail: error processing message uid=%s", uid, exc_info=True)

        mail.logout()

    except Exception:
        logger.exception("Gmail poll failed")

    _last_checked = now
    return messages
