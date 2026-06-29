import logging
from telegram import Update

logger = logging.getLogger(__name__)


async def safe_reply(update: Update, text: str) -> None:
    """Send reply with Markdown; fall back to plain text if parse fails."""
    try:
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception:
        try:
            await update.message.reply_text(text)
        except Exception:
            logger.exception("Failed to send reply even as plain text")
