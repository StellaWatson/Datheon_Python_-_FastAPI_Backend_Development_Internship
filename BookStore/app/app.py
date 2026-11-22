from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    User,
    Book,
    get_db,
    create_tables,
    close_database
)

from app.schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    BookCreate,
    BookResponse,
    BookUpdate
)

from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

from app.modules import (
    get_user_by_email,
    get_book_by_id
)

from app.admin import router as admin_router
from app.notifications import dispatch_webhook, send_welcome_email
from app.rate_limit import api_rate_limiter, auth_rate_limiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not getattr(app.state, "testing", False):
        await create_tables()

    yield

    if not getattr(app.state, "testing", False):
        await close_database()
app = FastAPI(
    title="BookStore API",
    description="A BookStore API built with FastAPI",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(admin_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# -------------------------
# AUTHENTICATION
# -------------------------

@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=HTTPStatus.CREATED,
    tags=["Auth"],
    dependencies=[Depends(auth_rate_limiter)]
)
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    existing_user = await get_user_by_email(
        user_data.email,
        db
    )

    if existing_user:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Email is already registered"
        )

    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )

    existing_username = result.scalar_one_or_none()

    if existing_username:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Username is already taken"
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password)
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Runs after the response is sent; the client does not wait for these.
    background_tasks.add_task(
        send_welcome_email, new_user.email, new_user.username
    )
    background_tasks.add_task(
        dispatch_webhook,
        "user.registered",
        {"user_id": new_user.id, "username": new_user.username}
    )

    return new_user


@app.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["Auth"],
    dependencies=[Depends(auth_rate_limiter)]
)
async def login_user(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(
        login_data.email,
        db
    )

    if not user or not verify_password(
        login_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="User account is inactive"
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.get(
    "/auth/me",
    response_model=UserResponse,
    tags=["Auth"]
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user


# -------------------------
# BOOKS
# -------------------------

@app.get(
    "/books",
    response_model=list[BookResponse],
    tags=["Books"],
    dependencies=[Depends(api_rate_limiter)]
)
async def get_books(
    author: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: Literal["title", "price"] = "title",
    order: Literal["asc", "desc"] = "asc",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Book).where(
        Book.user_id == current_user.id
    )

    if author:
        query = query.where(
            Book.author.ilike(f"%{author}%")
        )

    sort_column = (
        Book.title if sort_by == "title"
        else Book.price
    )

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)

    return result.scalars().all()


@app.get(
    "/books/{book_id}",
    response_model=BookResponse,
    tags=["Books"],
    dependencies=[Depends(api_rate_limiter)]
)
async def get_specific_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    book = await get_book_by_id(
        book_id,
        current_user.id,
        db
    )

    if book is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Book not found"
        )

    return book


@app.post(
    "/books",
    response_model=BookResponse,
    status_code=HTTPStatus.CREATED,
    tags=["Books"],
    dependencies=[Depends(api_rate_limiter)]
)
async def create_book(
    book_data: BookCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_book = Book(
        title=book_data.title,
        author=book_data.author,
        price=book_data.price,
        user_id=current_user.id
    )

    db.add(new_book)
    await db.commit()
    await db.refresh(new_book)

    background_tasks.add_task(
        dispatch_webhook,
        "book.created",
        BookResponse.model_validate(new_book).model_dump()
    )

    return new_book


@app.put(
    "/books/{book_id}",
    response_model=BookResponse,
    status_code=HTTPStatus.OK,
    tags=["Books"],
    dependencies=[Depends(api_rate_limiter)]
)
async def update_book(
    book_id: int,
    book_data: BookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    book = await get_book_by_id(
        book_id,
        current_user.id,
        db
    )

    if book is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Book not found"
        )

    book.title = book_data.title
    book.author = book_data.author
    book.price = book_data.price

    await db.commit()
    await db.refresh(book)

    return book


@app.delete(
    "/books/{book_id}",
    status_code=HTTPStatus.OK,
    tags=["Books"],
    dependencies=[Depends(api_rate_limiter)]
)
async def delete_book(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    book = await get_book_by_id(
        book_id,
        current_user.id,
        db
    )

    if book is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Book not found"
        )

    await db.delete(book)
    await db.commit()

    background_tasks.add_task(
        dispatch_webhook,
        "book.deleted",
        {"id": book_id, "user_id": current_user.id}
    )

    return {"message": "Book deleted successfully"}