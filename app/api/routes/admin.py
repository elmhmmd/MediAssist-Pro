from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import User
from app.schemas.user import UserOut
from app.services.admin import delete_user, get_global_stats, list_users, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def get_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list_users(db)


@router.delete("/users/{user_id}", status_code=204)
def remove_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    delete_user(db, user_id)


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return get_global_stats(db)
