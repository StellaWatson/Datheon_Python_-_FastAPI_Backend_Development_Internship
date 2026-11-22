"""
Promote an existing user to admin.

    uv run python make_admin.py user@example.com
    docker compose exec api python make_admin.py user@example.com
"""
import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal, Role, User, close_database


async def promote(email: str) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"No user with email {email!r}. Register first via /auth/register.")
            return 1

        user.role = Role.ADMIN.value
        await db.commit()
        print(f"{user.username} ({email}) is now an admin.")

    await close_database()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(promote(sys.argv[1])))
