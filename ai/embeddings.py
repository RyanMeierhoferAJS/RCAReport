import openai
from config import OPENAI_API_KEY

_client = openai.OpenAI(api_key=OPENAI_API_KEY)
_MODEL = "text-embedding-3-small"


def embed(text: str) -> list[float]:
    text = text.replace("\n", " ").strip()
    if not text:
        return []
    response = _client.embeddings.create(model=_MODEL, input=text)
    return response.data[0].embedding


def embed_task(title: str, description: str | None, project: str | None, owner: str | None) -> list[float]:
    return embed(" ".join(filter(None, [title, description, project, owner])))


def embed_decision(title: str, description: str | None, reason: str | None, project: str | None) -> list[float]:
    return embed(" ".join(filter(None, [title, description, reason, project])))


def embed_career_event(type: str, title: str, description: str | None, project: str | None) -> list[float]:
    return embed(" ".join(filter(None, [type, title, description, project])))


def embed_note(content: str, tags: list[str], entities: list[str], project: str | None) -> list[float]:
    parts = [content, project] + tags + entities
    return embed(" ".join(filter(None, parts)))
