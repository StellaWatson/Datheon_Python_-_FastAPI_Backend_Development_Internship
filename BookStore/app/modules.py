from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Book, User


async def get_user_by_email(
    email: str,
    db: AsyncSession
):
    result = await db.execute(
        select(User).where(User.email == email)
    )

    return result.scalar_one_or_none()


async def get_book_by_id(
    book_id: int,
    user_id: int,
    db: AsyncSession
):
    result = await db.execute(
        select(Book).where(
            Book.id == book_id,
            Book.user_id == user_id
        )
    )

    return result.scalar_one_or_none()