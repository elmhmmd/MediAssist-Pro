from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Query, User
from app.services.auth import get_current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def list_users(db: Session) -> list[User]:
    return db.query(User).all()


def delete_user(db: Session, user_id: int) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


def get_global_stats(db: Session) -> dict:
    total_users = db.query(User).count()
    total_queries = db.query(Query).count()
    admin_count = db.query(User).filter(User.role == "admin").count()
    return {
        "total_users": total_users,
        "total_queries": total_queries,
        "admin_count": admin_count,
    }
