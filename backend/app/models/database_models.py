from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func, Boolean
from typing import List, Optional
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invitation_code: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    invitation_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    categories: Mapped[List["Category"]] = relationship(back_populates="user")
    progresses: Mapped[List["ReadingProgress"]] = relationship(back_populates="user")

class Book(Base):
    __tablename__ = "books"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String)
    cover_path: Mapped[Optional[str]] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    sync_hash: Mapped[Optional[str]] = mapped_column(String)
    last_sync: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    progresses: Mapped[List["ReadingProgress"]] = relationship(back_populates="book")

class Category(Base):
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String)  # 'system' or 'user'
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    
    user: Mapped[Optional["User"]] = relationship(back_populates="categories")

class BookCategoryRel(Base):
    __tablename__ = "book_category_rel"
    
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    
    __table_args__ = (
        UniqueConstraint("book_id", "category_id", "user_id", name="uq_book_cat_user"),
    )

class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), primary_key=True)
    current_page: Mapped[int] = mapped_column(Integer, default=1)
    last_read_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_completed: Mapped[int] = mapped_column(Integer, default=0)
    
    user: Mapped["User"] = relationship(back_populates="progresses")
    book: Mapped["Book"] = relationship(back_populates="progresses")
