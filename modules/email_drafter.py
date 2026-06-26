"""
Saves email drafts to Gmail (IMAP APPEND) or AJS Outlook (Graph API).
"""
import imaplib
import logging
import time
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _find_drafts_folder(mail: imaplib.IMAP4_SSL) -> str:
    """Locate the Drafts folder by its \\Drafts flag (locale-safe)."""
    _, folders = mail.list()
    for entry in (folders or []):
        if not entry:
            continue
        decoded = entry.decode() if isinstance(entry, bytes) else entry
        if "\\Drafts" in decoded:
            # Extract folder name — last quoted segment or last token
            parts = decoded.split('"')
            if len(parts) >= 2:
                return parts[-2]
    return "[Gmail]/Drafts"


def save_gmail_draft(to_addr: str, subject: str, body: str) -> bool:
    from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD):
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = to_addr or ""
        msg["Subject"] = subject

        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        folder = _find_drafts_folder(mail)
        mail.append(
            folder,
            "\\Draft",
            imaplib.Time2Internaldate(time.time()),
            msg.as_bytes(),
        )
        mail.logout()
        logger.info("Gmail draft saved: %s → %s", subject, to_addr)
        return True
    except Exception:
        logger.error("Gmail draft save failed", exc_info=True)
        return False


def save_graph_draft(to_addr: str, subject: str, body: str) -> bool:
    """Save draft to AJS Outlook via Graph API (requires /connect token)."""
    try:
        import requests
        from modules.graph import _get_token, _GRAPH_BASE
        token = _get_token()
        if not token:
            return False
        payload = {
            "subject": subject,
            "isDraft": True,
            "body": {"contentType": "Text", "content": body},
        }
        if to_addr:
            payload["toRecipients"] = [{"emailAddress": {"address": to_addr}}]
        resp = requests.post(
            f"{_GRAPH_BASE}/me/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Graph draft saved: %s → %s", subject, to_addr)
        return True
    except Exception:
        logger.error("Graph draft save failed", exc_info=True)
        return False


def save_draft(account: str, to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    """
    Save to the appropriate account. Returns (success, account_label).
    Falls back to Gmail if Graph isn't connected.
    """
    if account == "ajs":
        if save_graph_draft(to_addr, subject, body):
            return True, "AJS Outlook"
        # Fallback to Gmail with a note
        logger.info("Graph not connected — falling back to Gmail draft")
        if save_gmail_draft(to_addr, subject, body):
            return True, "Gmail (AJS Graph not connected)"
        return False, ""
    else:
        if save_gmail_draft(to_addr, subject, body):
            return True, "Gmail"
        return False, ""
