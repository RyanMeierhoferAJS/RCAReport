import logging
from telegram import Update
from telegram.ext import ContextTypes
from modules import tasks, decisions, career
from modules.digest import get_daily_digest
from modules.weekly_report import get_weekly_report
from modules.search import search_and_answer, build_context_from_results
from ai.router import deep_analysis
from db import client as db

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*PIA — Personal Intelligence Agent*\n\n"
        "Send me anything naturally — I'll extract tasks, decisions and achievements automatically.\n\n"
        "*Commands*\n"
        "/tasks — open tasks\n"
        "/decisions — recent decisions\n"
        "/career — career journal\n"
        "/digest — morning briefing\n"
        "/report — weekly report\n"
        "/search \\[query\\] — search memory\n"
        "/think \\[prompt\\] — deep analysis\n"
        "/deep \\[prompt\\] — deep analysis\n"
        "/help — show this",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(tasks.get_formatted_open_tasks(), parse_mode="Markdown")


async def cmd_decisions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(decisions.get_formatted_decisions(), parse_mode="Markdown")


async def cmd_career(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(career.get_career_summary(), parse_mode="Markdown")


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("_Generating your briefing…_", parse_mode="Markdown")
    await update.message.reply_text(get_daily_digest(), parse_mode="Markdown")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("_Generating weekly report…_", parse_mode="Markdown")
    await update.message.reply_text(get_weekly_report(), parse_mode="Markdown")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /search \\[your query\\]", parse_mode="Markdown")
        return
    await update.message.reply_text(f"_Searching for: {query}…_", parse_mode="Markdown")
    await update.message.reply_text(search_and_answer(query), parse_mode="Markdown")


async def cmd_think(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            "Usage: /think \\[topic or question\\]", parse_mode="Markdown"
        )
        return

    await update.message.reply_text("_Deep analysis in progress…_", parse_mode="Markdown")
    results = db.full_search(query)
    ctx_text = build_context_from_results(results)
    result = deep_analysis(query, ctx_text or "No relevant context found in memory.")
    await update.message.reply_text(result, parse_mode="Markdown")
