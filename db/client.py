from datetime import date, datetime
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ── Captures ──────────────────────────────────────────────────────────────────

def store_capture(raw_text: str, telegram_msg_id: int | None = None,
                  telegram_chat_id: int | None = None, media_type: str = "text") -> str:
    result = get_client().table("captures").insert({
        "raw_text": raw_text,
        "telegram_msg_id": telegram_msg_id,
        "telegram_chat_id": telegram_chat_id,
        "media_type": media_type,
    }).execute()
    return result.data[0]["id"]


# ── Tasks ─────────────────────────────────────────────────────────────────────

def create_task(title: str, description: str | None = None, priority: str = "medium",
                due_date: str | None = None, project: str | None = None,
                source_capture_id: str | None = None) -> dict:
    from ai.embeddings import embed_task
    embedding = embed_task(title, description, project, "Ryan")
    result = get_client().table("tasks").insert({
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "project": project,
        "source_capture_id": source_capture_id,
        "embedding": embedding,
    }).execute()
    return result.data[0]


def get_open_tasks() -> list[dict]:
    result = (
        get_client().table("tasks")
        .select("id, title, description, priority, status, due_date, project, owner")
        .in_("status", ["open", "in_progress", "waiting"])
        .order("priority")
        .order("created_at")
        .execute()
    )
    return result.data


def complete_task_by_id(task_id: str) -> dict:
    result = (
        get_client().table("tasks")
        .update({"status": "complete", "completed_at": datetime.utcnow().isoformat()})
        .eq("id", task_id)
        .execute()
    )
    return result.data[0]


def semantic_search_tasks(embedding: list[float], threshold: float = 0.45) -> list[dict]:
    result = get_client().rpc("semantic_search_tasks", {
        "query_embedding": embedding,
        "similarity_threshold": threshold,
        "match_count": 10,
    }).execute()
    return result.data


# ── Decisions ─────────────────────────────────────────────────────────────────

def create_decision(title: str, description: str | None = None, reason: str | None = None,
                    alternatives: list[str] | None = None, project: str | None = None,
                    source_capture_id: str | None = None) -> dict:
    from ai.embeddings import embed_decision
    embedding = embed_decision(title, description, reason, project)
    result = get_client().table("decisions").insert({
        "title": title,
        "description": description,
        "reason": reason,
        "alternatives": alternatives or [],
        "project": project,
        "source_capture_id": source_capture_id,
        "embedding": embedding,
    }).execute()
    return result.data[0]


def get_recent_decisions(limit: int = 10) -> list[dict]:
    result = (
        get_client().table("decisions")
        .select("id, title, description, reason, alternatives, project, decided_at")
        .order("decided_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def semantic_search_decisions(embedding: list[float], threshold: float = 0.45) -> list[dict]:
    result = get_client().rpc("semantic_search_decisions", {
        "query_embedding": embedding,
        "similarity_threshold": threshold,
        "match_count": 10,
    }).execute()
    return result.data


# ── Career Journal ────────────────────────────────────────────────────────────

def create_career_event(type: str, title: str, description: str | None = None,
                        value_pounds: float | None = None, project: str | None = None,
                        source_capture_id: str | None = None) -> dict:
    from ai.embeddings import embed_career_event
    embedding = embed_career_event(type, title, description, project)
    result = get_client().table("career_events").insert({
        "type": type,
        "title": title,
        "description": description,
        "value_pounds": value_pounds,
        "project": project,
        "source_capture_id": source_capture_id,
        "embedding": embedding,
    }).execute()
    return result.data[0]


def get_career_events(year: int | None = None, limit: int = 50) -> list[dict]:
    q = (
        get_client().table("career_events")
        .select("id, type, title, description, value_pounds, project, event_date")
        .order("event_date", desc=True)
    )
    if year:
        q = q.gte("event_date", f"{year}-01-01").lte("event_date", f"{year}-12-31")
    return q.limit(limit).execute().data


def semantic_search_career(embedding: list[float], threshold: float = 0.45) -> list[dict]:
    result = get_client().rpc("semantic_search_career", {
        "query_embedding": embedding,
        "similarity_threshold": threshold,
        "match_count": 10,
    }).execute()
    return result.data


# ── Notes ─────────────────────────────────────────────────────────────────────

def create_note(content: str, tags: list[str] | None = None,
                entities: list[str] | None = None, project: str | None = None,
                source_capture_id: str | None = None) -> dict:
    from ai.embeddings import embed_note
    embedding = embed_note(content, tags or [], entities or [], project)
    result = get_client().table("notes").insert({
        "content": content,
        "tags": tags or [],
        "entities": entities or [],
        "project": project,
        "source_capture_id": source_capture_id,
        "embedding": embedding,
    }).execute()
    return result.data[0]


def semantic_search_notes(embedding: list[float], threshold: float = 0.45) -> list[dict]:
    result = get_client().rpc("semantic_search_notes", {
        "query_embedding": embedding,
        "similarity_threshold": threshold,
        "match_count": 10,
    }).execute()
    return result.data


# ── Projects ──────────────────────────────────────────────────────────────────

def get_active_projects() -> list[dict]:
    result = (
        get_client().table("projects")
        .select("*")
        .eq("status", "active")
        .order("last_activity", desc=True)
        .execute()
    )
    return result.data


def update_project_activity(project_name: str) -> None:
    get_client().table("projects").update({
        "last_activity": datetime.utcnow().isoformat()
    }).ilike("name", f"%{project_name}%").execute()


# ── Semantic search across all tables ─────────────────────────────────────────

def full_search(query: str) -> dict[str, list[dict]]:
    from ai.embeddings import embed
    query_embedding = embed(query)
    return {
        "tasks":         semantic_search_tasks(query_embedding),
        "decisions":     semantic_search_decisions(query_embedding),
        "career_events": semantic_search_career(query_embedding),
        "notes":         semantic_search_notes(query_embedding),
    }


# ── Report storage ────────────────────────────────────────────────────────────

def store_weekly_report(content: str, week_ending: date) -> None:
    get_client().table("weekly_reports").insert({
        "content": content,
        "week_ending": week_ending.isoformat(),
    }).execute()


def store_daily_digest(content: str, digest_date: date) -> None:
    get_client().table("daily_digests").insert({
        "content": content,
        "digest_date": digest_date.isoformat(),
    }).execute()
