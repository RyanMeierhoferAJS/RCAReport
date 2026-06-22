import json
import logging
from datetime import date
import anthropic
from config import ANTHROPIC_API_KEY, TIER_1_MODEL, TIER_2_MODEL, TIER_3_MODEL
from ai.prompts import (
    EXTRACTION_SYSTEM, QUESTION_SYSTEM,
    DIGEST_SYSTEM, WEEKLY_REPORT_SYSTEM, DEEP_SYSTEM,
)

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _call(model: str, system: str, user: str, max_tokens: int = 1024) -> str:
    response = _client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def extract_from_message(text: str) -> dict:
    today = date.today().isoformat()
    system = EXTRACTION_SYSTEM.format(today=today)
    raw = _call(TIER_1_MODEL, system, text)

    # Strip markdown fences if Haiku adds them
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Tier 1 JSON parse failed, returning minimal structure")
        return {
            "classification": "general",
            "tasks": [], "decisions": [], "achievements": [], "notes": [],
            "projects_mentioned": [],
            "response": "Got it, stored.",
        }


def answer_question(question: str, context: str) -> str:
    today = date.today().isoformat()
    system = QUESTION_SYSTEM.format(today=today, context=context)
    return _call(TIER_2_MODEL, system, question, max_tokens=1024)


def generate_digest(context: str) -> str:
    today = date.today()
    system = DIGEST_SYSTEM.format(
        today=today.isoformat(),
        day_of_week=today.strftime("%A"),
    )
    return _call(TIER_2_MODEL, system, f"Generate my morning briefing.\n\n{context}", max_tokens=1200)


def generate_weekly_report(context: str) -> str:
    system = WEEKLY_REPORT_SYSTEM.format(week_ending=date.today().isoformat())
    return _call(TIER_2_MODEL, system, f"Generate my weekly report.\n\n{context}", max_tokens=2000)


def deep_analysis(query: str, context: str) -> str:
    today = date.today().isoformat()
    system = DEEP_SYSTEM.format(today=today, context=context)
    return _call(TIER_3_MODEL, system, query, max_tokens=3000)
