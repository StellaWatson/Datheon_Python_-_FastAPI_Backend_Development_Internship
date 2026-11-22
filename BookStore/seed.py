import asyncio

from sqlalchemy import select

from app.database import (
    AsyncSessionLocal,
    User,
    Book,
    create_tables
)

from app.security import hash_password


async def seed_database():
    await create_tables()

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(User).where(
                User.email == "user@example.com"
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                username="bookstore_user",
                email="user@example.com",
                hashed_password=hash_password("stringst")
            )

            db.add(user)
            await db.commit()
            await db.refresh(user)

        result = await db.execute(
            select(Book).where(Book.user_id == user.id)
        )

        existing_books = result.scalars().first()

        if existing_books:
            print("Books already exist for this user.")
            return

        books = [
            ("Clean Code", "Robert C. Martin", 25.0),
            ("The Pragmatic Programmer", "Andrew Hunt", 30.0),
            ("Python Crash Course", "Eric Matthes", 28.0),
            ("Atomic Habits", "James Clear", 20.0),
            ("Deep Work", "Cal Newport", 22.0),
            ("The Clean Coder", "Robert C. Martin", 24.0),
            ("Fluent Python", "Luciano Ramalho", 35.0),
            ("Effective Python", "Brett Slatkin", 32.0),
            ("Think Python", "Allen Downey", 18.0),
            ("Design Patterns", "Erich Gamma", 40.0),
            ("Refactoring", "Martin Fowler", 38.0),
            ("Code Complete", "Steve McConnell", 42.0),
            ("The Mythical Man-Month", "Frederick Brooks", 27.0),
            ("Introduction to Algorithms", "Thomas H. Cormen", 50.0),
            ("Head First Java", "Kathy Sierra", 29.0),
            ("Learning SQL", "Alan Beaulieu", 26.0),
            ("Eloquent JavaScript", "Marijn Haverbeke", 23.0),
            ("The Art of Computer Programming", "Donald Knuth", 60.0),
            ("You Don't Know JS", "Kyle Simpson", 21.0),
            ("Grokking Algorithms", "Aditya Bhargava", 25.0)
        ]

        for title, author, price in books:
            db.add(
                Book(
                    title=title,
                    author=author,
                    price=price,
                    user_id=user.id
                )
            )

        await db.commit()

        print("20 books added successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())