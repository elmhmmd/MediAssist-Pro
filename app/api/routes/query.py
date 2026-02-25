from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Query, User
from app.schemas.query import QueryOut, QueryRequest
from app.services.auth import get_current_user
from app.services.rag import handle_query

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryOut)
def ask(
    request: QueryRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return handle_query(request.question, db)


@router.get("/history", response_model=list[QueryOut])
def history(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(Query).order_by(Query.created_at.desc()).all()
