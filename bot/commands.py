import logging
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes
from modules import tasks, decisions, career
from modules.digest import get_daily_digest
from modules.weekly_report import get_weekly_report
from modules.search import search_and_answer, build_context_from_results
from modules.ideas import get_formatted_ideas, format_ideas_for_export
from modules.pdp import get_pdp_summary, format_pdp_for_export, format_pdp_for_ai_analysis
from modules.calendar_feed import get_today_events, get_tomorrow_events, format_events
from ai.router import deep_analysis, analyse_pdp, generate_export
from db import client as db

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*PIA — Personal Intelligence Agent*\n\n"
        "Send me anything naturally — I'll extract tasks, decisions, achievements and ideas automatically.\n\n"
        "*Capture*\n"
        "/tasks — open tasks\n"
        "/done \\[number or title\\] — complete a task\n"
        "/today — today's calendar \\+ tomorrow preview\n"
        "/decisions — recent decisions\n"
        "/career — career journal\n"
        "/ideas — idea bank\n"
        "/pdp — development plan\n\n"
        "*Reporting*\n"
        "/digest — morning briefing\n"
        "/report — weekly report\n"
        "/search \\[query\\] — search memory\n"
        "/think \\[prompt\\] — deep analysis\n\n"
        "*AI Exports*\n"
        "/export — Claude Code context block\n"
        "/pdp analyse — AI review of your PDP progress\n\n"
        "/help — show this",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(tasks.get_formatted_open_tasks(), parse_mode="Markdown")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = " ".join(context.args).strip() if context.args else ""
    if not arg:
        await update.message.reply_text(
            "Usage: `/done 3` or `/done partial title`", parse_mode="Markdown"
        )
        return

    open_tasks = db.get_open_tasks()

    # Number-based: /done 2
    if arg.isdigit():
        idx = int(arg) - 1
        if idx < 0 or idx >= len(open_tasks):
            await update.message.reply_text(f"No task number {arg}. Use /tasks to see the list.")
            return
        task = open_tasks[idx]
        db.complete_task_by_id(task["id"])
        await update.message.reply_text(f"✅ Done: *{task['title']}*", parse_mode="Markdown")
        return

    # Title-based: /done partial title — try DB ilike first, fall back to Python filter
    matches = db.find_open_tasks_by_title(arg)
    if not matches:
        # Broader Python filter over already-fetched open tasks
        lower = arg.lower()
        matches = [t for t in open_tasks if lower in t["title"].lower()]

    if not matches:
        await update.message.reply_text(
            f"No open task matching *{arg}*\. Use /tasks to see what's open.",
            parse_mode="Markdown",
        )
        return

    if len(matches) == 1:
        db.complete_task_by_id(matches[0]["id"])
        await update.message.reply_text(f"✅ Done: *{matches[0]['title']}*", parse_mode="Markdown")
        return

    # Multiple matches — ask for clarification
    options = "\n".join(f"{i+1}. {t['title']}" for i, t in enumerate(matches[:5]))
    await update.message.reply_text(
        f"Multiple matches — which one?\n\n{options}\n\nReply `/done <number>`",
        parse_mode="Markdown",
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_events    = get_today_events()
    tomorrow_events = get_tomorrow_events()

    parts = [f"*Schedule — {date.today().strftime('%A %-d %B')}*\n"]

    if today_events:
        parts.append(format_events(today_events))
    else:
        parts.append("_No meetings today_")

    if tomorrow_events:
        parts.append(f"\n*Tomorrow*\n{format_events(tomorrow_events)}")

    if not today_events and not tomorrow_events:
        parts.append("\n_Calendar feeds not configured yet — add iCal URLs to Railway env vars_")

    await update.message.reply_text("\n".join(parts), parse_mode="Markdown")


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


async def cmd_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status_filter = context.args[0].lower() if context.args else None
    valid = {"raw", "refined", "parked", "shipped"}
    if status_filter and status_filter not in valid:
        await update.message.reply_text(
            "Usage: /ideas \\[raw|refined|parked|shipped\\]", parse_mode="Markdown"
        )
        return
    await update.message.reply_text(get_formatted_ideas(status_filter), parse_mode="Markdown")


async def cmd_pdp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []

    if not args:
        await update.message.reply_text(get_pdp_summary(), parse_mode="Markdown")
        return

    subcmd = args[0].lower()

    if subcmd == "add":
        rest = " ".join(args[1:])
        parts = [p.strip() for p in rest.split("|")]
        if not parts[0]:
            await update.message.reply_text(
                "Usage: `/pdp add Title | category | objective`\n"
                "Categories: leadership, technical, commercial, personal",
                parse_mode="Markdown",
            )
            return
        title = parts[0]
        category = parts[1] if len(parts) > 1 else "general"
        objective = parts[2] if len(parts) > 2 else None
        db.create_pdp_action(title=title, category=category, objective=objective)
        await update.message.reply_text(f"✅ PDP action added: *{title}*", parse_mode="Markdown")

    elif subcmd in ("analyse", "analyze"):
        await update.message.reply_text("_Analysing your PDP…_", parse_mode="Markdown")
        actions = db.get_pdp_actions()
        if not actions:
            await update.message.reply_text(
                "No PDP actions yet. Add one with `/pdp add`.", parse_mode="Markdown"
            )
            return
        pdp_text = format_pdp_for_ai_analysis(actions)
        result = analyse_pdp(pdp_text)
        await update.message.reply_text(result, parse_mode="Markdown")

    elif subcmd == "exceeded":
        rest = " ".join(args[1:])
        parts = [p.strip() for p in rest.split("|")]
        if len(parts) < 2:
            await update.message.reply_text(
                "Usage: `/pdp exceeded Title | evidence of exceeding`",
                parse_mode="Markdown",
            )
            return
        action_title, evidence_text = parts[0], parts[1]
        actions = db.get_pdp_actions()
        matched = next(
            (a for a in actions if action_title.lower() in a["title"].lower()), None
        )
        if not matched:
            await update.message.reply_text(
                f"No PDP action found matching: {action_title}", parse_mode="Markdown"
            )
            return
        db.add_pdp_evidence(matched["id"], evidence_text, new_status="exceeded")
        await update.message.reply_text(
            f"⭐ Marked as *exceeded*: {matched['title']}\nEvidence: _{evidence_text}_",
            parse_mode="Markdown",
        )

    else:
        await update.message.reply_text(
            "*PDP commands:*\n"
            "/pdp — dashboard\n"
            "/pdp add Title | category | objective\n"
            "/pdp exceeded Title | evidence\n"
            "/pdp analyse — AI analysis of your progress",
            parse_mode="Markdown",
        )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("_Generating Claude Code context export…_", parse_mode="Markdown")

    ideas = db.get_ideas(limit=30)
    pdp_actions = db.get_pdp_actions()
    open_tasks = db.get_open_tasks()

    ideas_text = format_ideas_for_export(ideas)
    pdp_text = format_pdp_for_export(pdp_actions)

    top_tasks = "\n".join(
        f"• [{t.get('priority', 'med').upper()}] {t['title']}"
        + (f" ({t['project']})" if t.get("project") else "")
        for t in open_tasks[:10]
    ) or "No open tasks."

    data = f"""DATE: {date.today().isoformat()}

OPEN TASKS (top 10):
{top_tasks}

IDEAS:
{ideas_text}

PDP ACTIONS:
{pdp_text}
"""

    export_block = generate_export(data)
    header = f"*PIA Brain Export — {date.today().isoformat()}*\nPaste this at the start of a Claude Code session:\n\n"
    await update.message.reply_text(header + f"```\n{export_block}\n```", parse_mode="Markdown")
