import asyncio
import logging
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes
from modules import tasks, decisions, career
from modules.projects import get_project_dashboard
from modules.digest import get_daily_digest
from modules.weekly_report import get_weekly_report
from modules.search import search_and_answer, build_context_from_results
from modules.ideas import get_formatted_ideas, format_ideas_for_export
from modules.pdp import get_pdp_summary, format_pdp_for_export, format_pdp_for_ai_analysis
from modules.calendar_feed import get_today_events, get_tomorrow_events, format_events
from ai.router import deep_analysis, analyse_pdp, generate_export, draft_email
from db import client as db
from bot.utils import safe_reply

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*PIA — Personal Intelligence Agent*\n\n"
        "Send me anything naturally — I'll extract tasks, decisions, achievements and ideas automatically.\n\n"
        "*Capture*\n"
        "/tasks — open tasks\n"
        "/done \\[number or title\\] — complete a task\n"
        "/meeting — log meeting notes \\(extracts actions \\+ decisions\\)\n"
        "/today — today's calendar \\+ tomorrow preview\n"
        "/projects — project dashboard\n"
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
        "/status — quick snapshot \\(meetings \\+ top tasks\\)\n\n"
        "*Email*\n"
        "/draft — draft an email \\(saves to Gmail or Outlook drafts\\)\n"
        "/reply — draft an email reply\n\n"
        "*Integrations*\n"
        "/connect — link Microsoft 365 \\(calendar \\+ email\\)\n\n"
        "/help — show this",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await safe_reply(update, tasks.get_formatted_open_tasks())


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
    await safe_reply(update, decisions.get_formatted_decisions())


async def cmd_career(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await safe_reply(update, career.get_career_summary())


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("_Generating your briefing…_", parse_mode="Markdown")
    await safe_reply(update, get_daily_digest())


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("_Generating weekly report…_", parse_mode="Markdown")
    await safe_reply(update, get_weekly_report())


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /search \\[your query\\]", parse_mode="Markdown")
        return
    await update.message.reply_text(f"_Searching for: {query}…_", parse_mode="Markdown")
    await safe_reply(update, search_and_answer(query))


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
    await safe_reply(update, result)


async def cmd_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status_filter = context.args[0].lower() if context.args else None
    valid = {"raw", "refined", "parked", "shipped"}
    if status_filter and status_filter not in valid:
        await update.message.reply_text(
            "Usage: /ideas \\[raw|refined|parked|shipped\\]", parse_mode="Markdown"
        )
        return
    await safe_reply(update, get_formatted_ideas(status_filter))


async def cmd_pdp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []

    if not args:
        await safe_reply(update, get_pdp_summary())
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
        await safe_reply(update, result)

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


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_events    = get_today_events()
    open_tasks      = db.get_open_tasks()
    due             = db.get_due_tasks()
    overdue_count   = len(due["overdue"])
    due_today_count = len(due["due_today"])

    lines = [f"*Status — {date.today().strftime('%A %-d %B')}*\n"]

    if today_events:
        lines.append("*Meetings*")
        lines.append(format_events(today_events))
    else:
        lines.append("_No meetings today_")

    lines.append("\n*Top tasks*")
    if open_tasks:
        for t in open_tasks[:3]:
            pri  = f"[{t['priority'].upper()}] " if t.get("priority") else ""
            proj = f" ({t['project']})" if t.get("project") else ""
            lines.append(f"• {pri}{t['title']}{proj}")
        if len(open_tasks) > 3:
            lines.append(f"_…{len(open_tasks) - 3} more — /tasks_")
    else:
        lines.append("_All clear_ ✓")

    if overdue_count:
        lines.append(f"\n⚠️ *{overdue_count} overdue* — use /tasks to review")
    elif due_today_count:
        lines.append(f"\n📅 *{due_today_count} due today*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await safe_reply(update, get_project_dashboard())


async def cmd_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notes = " ".join(context.args) if context.args else ""
    if not notes:
        await update.message.reply_text(
            "Usage: /meeting with [name] about [topic] — [key points, decisions, actions]\n\n"
            "Example: /meeting with Mark re HVAC — agreed £45k budget, "
            "action: send PO by Friday, Mark to provide maintenance schedule",
        )
        return

    await update.message.reply_text("_Processing meeting notes…_", parse_mode="Markdown")

    # Hint the extraction engine this is a meeting — improves decision/task detection
    hinted = f"MEETING NOTES: {notes}"
    extracted = db.store_capture(raw_text=hinted, media_type="text")

    from ai.router import extract_from_message
    result = extract_from_message(hinted)

    stored = []
    for task in result.get("tasks", []):
        db.create_task(
            title=task["title"],
            description=task.get("description"),
            priority=task.get("priority", "medium"),
            due_date=task.get("due_date"),
            project=task.get("project"),
            source_capture_id=extracted,
        )
        stored.append(f"✅ *Action:* {task['title']}")

    for decision in result.get("decisions", []):
        db.create_decision(
            title=decision["title"],
            description=decision.get("description"),
            reason=decision.get("reason"),
            alternatives=decision.get("alternatives", []),
            project=decision.get("project"),
            source_capture_id=extracted,
        )
        stored.append(f"🎯 *Decision:* {decision['title']}")

    for achievement in result.get("achievements", []):
        db.create_career_event(
            type=achievement.get("type", "achievement"),
            title=achievement["title"],
            description=achievement.get("description"),
            value_pounds=achievement.get("value_pounds"),
            project=achievement.get("project"),
            source_capture_id=extracted,
        )
        stored.append(f"🏆 *Noted:* {achievement['title']}")

    for note in result.get("notes", []):
        db.create_note(
            content=note["content"],
            tags=note.get("tags", []) + ["meeting"],
            entities=note.get("entities", []),
            project=note.get("project"),
            source_capture_id=extracted,
        )

    if stored:
        reply = f"*Meeting logged*\n\n" + "\n".join(stored)
    else:
        reply = "_Meeting captured as a note — no specific actions or decisions detected._"

    await safe_reply(update, reply)


async def cmd_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.email_drafter import save_draft
    from modules.search import build_context_from_results
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        await update.message.reply_text(
            "Usage: /draft to [name/email] about [topic and key points]\n\n"
            "Example: /draft to Mark about the HVAC quote, need it by end of month"
        )
        return

    await update.message.reply_text("_Drafting email…_", parse_mode="Markdown")

    # Search memory for relevant context
    results = db.full_search(prompt)
    ctx_text = build_context_from_results(results)

    draft = draft_email(prompt, ctx_text)
    if not draft or not draft.get("subject"):
        await update.message.reply_text("Couldn't generate a draft — try being more specific.")
        return

    account    = draft.get("account", "gmail")
    to_addr    = draft.get("to_address") or ""
    to_name    = draft.get("to_name", to_addr)
    subject    = draft["subject"]
    body       = draft["body"]

    # Save to appropriate drafts folder
    saved, label = save_draft(account, to_addr, subject, body)

    # Send preview to Telegram
    to_line  = f"To: {to_name}" + (f" <{to_addr}>" if to_addr and to_addr != to_name else "")
    saved_line = f"_Saved to {label} Drafts_" if saved else "_Could not save to drafts — copy below_"

    preview = (
        f"*Draft ready*\n"
        f"{to_line}\n"
        f"Subject: {subject}\n"
        f"{saved_line}\n\n"
        f"```\n{body}\n```"
    )
    await safe_reply(update, preview)


async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.email_drafter import save_draft
    from modules.search import build_context_from_results
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        await update.message.reply_text(
            "Usage: /reply to [name] re [topic] — [what you want to say]\n\n"
            "Example: /reply to Mark re HVAC quote — ask for breakdown, mention £45k budget"
        )
        return

    await update.message.reply_text("_Drafting reply…_", parse_mode="Markdown")

    results  = db.full_search(prompt)
    ctx_text = build_context_from_results(results)
    draft    = draft_email(f"REPLY TO EMAIL: {prompt}", ctx_text)

    if not draft or not draft.get("subject"):
        await update.message.reply_text("Couldn't generate a reply — try being more specific.")
        return

    account  = draft.get("account", "gmail")
    to_addr  = draft.get("to_address") or ""
    to_name  = draft.get("to_name", to_addr)
    subject  = draft["subject"]
    body     = draft["body"]

    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    saved, label = save_draft(account, to_addr, subject, body)

    to_line    = f"To: {to_name}" + (f" <{to_addr}>" if to_addr and to_addr != to_name else "")
    saved_line = f"_Saved to {label} Drafts_" if saved else "_Could not save — copy below_"

    await safe_reply(
        update,
        f"*Reply ready*\n{to_line}\nSubject: {subject}\n{saved_line}\n\n```\n{body}\n```",
    )


async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.graph import start_device_code_flow, run_device_code_polling, _is_configured
    if not _is_configured():
        await update.message.reply_text(
            "❌ GRAPH_TENANT_ID and GRAPH_CLIENT_ID must be set in Railway env vars first."
        )
        return

    try:
        flow = start_device_code_flow()
    except Exception as exc:
        await update.message.reply_text(
            f"❌ Couldn't start Microsoft login: {exc}\n\n"
            "Check GRAPH_TENANT_ID and GRAPH_CLIENT_ID in Railway, and make sure "
            "'Allow public client flows' is enabled in your Azure app."
        )
        return

    user_code        = flow["user_code"]
    verification_uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")
    expires_in       = flow.get("expires_in", 900)
    interval         = flow.get("interval", 5)
    device_code      = flow["device_code"]

    await update.message.reply_text(
        f"🔗 Connect PIA to Microsoft 365\n\n"
        f"1. Open: {verification_uri}\n"
        f"2. Enter code: {user_code}\n"
        f"3. Sign in with ryan.meierhofer@ajsassetcare.co.uk\n\n"
        f"Code expires in {expires_in // 60} minutes. I'll notify you when connected."
    )

    asyncio.ensure_future(
        run_device_code_polling(context.application, device_code, interval, expires_in)
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
    await safe_reply(update, header + f"```\n{export_block}\n```")
