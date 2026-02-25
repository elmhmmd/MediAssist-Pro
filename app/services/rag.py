from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Query
from rag.rag_pipeline import ask


def handle_query(question: str, db: Session) -> Query:
    answer = ask(
        question,
        persist_directory=settings.CHROMA_DIR,
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
    record = Query(
        query=question,
        reponse=answer,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
