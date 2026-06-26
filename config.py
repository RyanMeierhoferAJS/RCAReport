import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_ALLOWED_USER_ID: int = int(os.environ["TELEGRAM_ALLOWED_USER_ID"])

ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]

# AI model tiers
TIER_1_MODEL = "claude-haiku-4-5-20251001"   # Extraction, classification (~90% of calls)
TIER_2_MODEL = "claude-sonnet-4-6"           # Reasoning, weekly reviews, Q&A synthesis
TIER_3_MODEL = "claude-opus-4-8"             # /think, /deep, RCA generation

USER_ID = "ryan"
TIMEZONE = "Europe/London"

# Microsoft Graph — AJS Outlook calendar + email (device code flow, no secret needed)
GRAPH_TENANT_ID:  str = os.environ.get("GRAPH_TENANT_ID", "")
GRAPH_CLIENT_ID:  str = os.environ.get("GRAPH_CLIENT_ID", "")
GRAPH_USER_EMAIL: str = os.environ.get("GRAPH_USER_EMAIL", "")

# Gmail IMAP — personal inbox email polling (app password, no OAuth)
GMAIL_ADDRESS:      str = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD: str = os.environ.get("GMAIL_APP_PASSWORD", "")

# Calendar iCal feeds — fallback / additional feeds (blank = skipped)
CALENDAR_FEEDS: list[tuple[str, str]] = [
    ("ASR",  os.environ.get("CALENDAR_ICAL_URL_ASR",  "")),
    ("Home", os.environ.get("CALENDAR_ICAL_URL_HOME", "")),
]
DIGEST_HOUR = 7     # 07:00 London daily digest
REPORT_DAY = "sun"  # Sunday weekly report
REPORT_HOUR = 8     # 08:00
