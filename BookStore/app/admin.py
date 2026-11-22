"""
Admin-only endpoints. Every route here requires role == "admin".
"""
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Book, Role, User, get_db
from app.notifications import notification_log
from app.rate_limit import api_rate_limiter
from app.schemas import (
    ActiveUpdate,
    NotificationRecord,
    RoleUpdate,
    UserResponse
)
from app.security import require_role


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[
        Depends(api_rate_limiter),
        Depends(require_role(Role.ADMIN))
    ]
)


async def _get_user_or_404(user_id: int, db: AsyncSession) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.get("/stats")
async def book_stats(db: AsyncSession = Depends(get_db)):
    """Books per user, computed with a JOIN + GROUP BY."""
    result = await db.execute(
        select(
            User.id,
            User.username,
            func.count(Book.id).label("book_count"),
            func.coalesce(func.sum(Book.price), 0).label("total_value")
        )
        .outerjoin(Book, Book.user_id == User.id)
        .group_by(User.id)
        .order_by(User.id)
    )

    return [
        {
            "user_id": row.id,
            "username": row.username,
            "book_count": row.book_count,
            "total_value": float(row.total_value)
        }
        for row in result
    ]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: int,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN))
):
    if user_id == current_user.id and body.role != Role.ADMIN:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Admins cannot remove their own admin role"
        )

    user = await _get_user_or_404(user_id, db)
    user.role = body.role.value
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/active", response_model=UserResponse)
async def set_active(
    user_id: int,
    body: ActiveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN))
):
    if user_id == current_user.id and not body.is_active:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Admins cannot deactivate themselves"
        )

    user = await _get_user_or_404(user_id, db)
    user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/notifications", response_model=list[NotificationRecord])
async def recent_notifications(limit: int = 20):
    """Most recent background jobs (emails / webhooks), newest first."""
    return list(reversed(notification_log))[:limit]
