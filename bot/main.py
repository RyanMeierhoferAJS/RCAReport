import logging
import pytz
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_ID,
    TIMEZONE, DIGEST_HOUR, REPORT_DAY, REPORT_HOUR,
)
from bot.handlers import handle_text, handle_voice, handle_document, error_handler
from bot.commands import (
    cmd_start, cmd_help, cmd_tasks, cmd_decisions, cmd_career,
    cmd_digest, cmd_report, cmd_search, cmd_think,
    cmd_ideas, cmd_pdp, cmd_export, cmd_done,
)
from modules.digest import get_daily_digest
from modules.weekly_report import get_weekly_report

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _send_digest(app: Application) -> None:
    try:
        text = get_daily_digest()
        await app.bot.send_message(
            chat_id=TELEGRAM_ALLOWED_USER_ID, text=text, parse_mode="Markdown"
        )
    except Exception:
        logger.exception("Scheduled digest failed")


async def _send_weekly_report(app: Application) -> None:
    try:
        text = get_weekly_report()
        await app.bot.send_message(
            chat_id=TELEGRAM_ALLOWED_USER_ID, text=text, parse_mode="Markdown"
        )
    except Exception:
        logger.exception("Scheduled weekly report failed")


async def _post_init(app: Application) -> None:
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        _send_digest,
        CronTrigger(hour=DIGEST_HOUR, minute=0, timezone=tz),
        args=[app],
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_weekly_report,
        CronTrigger(day_of_week=REPORT_DAY, hour=REPORT_HOUR, minute=0, timezone=tz),
        args=[app],
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — digest at %s:00, report on %s at %s:00", DIGEST_HOUR, REPORT_DAY, REPORT_HOUR)


def main() -> None:
    user_filter = filters.User(user_id=TELEGRAM_ALLOWED_USER_ID)

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start",     cmd_start,     filters=user_filter))
    app.add_handler(CommandHandler("help",      cmd_help,      filters=user_filter))
    app.add_handler(CommandHandler("tasks",     cmd_tasks,     filters=user_filter))
    app.add_handler(CommandHandler("done",      cmd_done,      filters=user_filter))
    app.add_handler(CommandHandler("decisions", cmd_decisions, filters=user_filter))
    app.add_handler(CommandHandler("career",    cmd_career,    filters=user_filter))
    app.add_handler(CommandHandler("digest",    cmd_digest,    filters=user_filter))
    app.add_handler(CommandHandler("report",    cmd_report,    filters=user_filter))
    app.add_handler(CommandHandler("search",    cmd_search,    filters=user_filter))
    app.add_handler(CommandHandler("think",     cmd_think,     filters=user_filter))
    app.add_handler(CommandHandler("deep",      cmd_think,     filters=user_filter))
    app.add_handler(CommandHandler("ideas",     cmd_ideas,     filters=user_filter))
    app.add_handler(CommandHandler("pdp",       cmd_pdp,       filters=user_filter))
    app.add_handler(CommandHandler("export",    cmd_export,    filters=user_filter))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, handle_text))
    app.add_handler(MessageHandler(filters.VOICE & user_filter, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL & user_filter, handle_document))

    app.add_error_handler(error_handler)

    logger.info("PIA starting — polling for updates")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
