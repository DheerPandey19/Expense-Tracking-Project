# Personal expense tracker — single-user, so no Profile/User model.
# Categories and expenses are global to the app (one implicit owner).

from datetime import date

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

expense_tags = Table(
    "expense_tags",
    Base.metadata,
    Column("expense_id", Integer, ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

expense_categories = Table(
    "expense_categories",
    Base.metadata,
    Column("expense_id", Integer, ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base):
    """Spending labels (Food, Rent, etc.). Names are unique app-wide."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#888888")

    expenses: Mapped[list["Expense"]] = relationship(
        secondary=expense_categories, back_populates="categories"
    )
    budget: Mapped["Budget | None"] = relationship(back_populates="category")


class Tag(Base):
    """Reusable freeform labels that can be attached to many expenses."""

    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", name="uq_tags_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)

    expenses: Mapped[list["Expense"]] = relationship(
        secondary=expense_tags, back_populates="tags"
    )


class Expense(Base):
    """One spending entry. All rows belong to the same (implicit) owner."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Primary category (first selection); also mirrored into categories M2M.
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(String(240), default="")

    categories: Mapped[list["Category"]] = relationship(
        secondary=expense_categories, back_populates="expenses"
    )
    tags: Mapped[list["Tag"]] = relationship(
        secondary=expense_tags, back_populates="expenses"
    )


class Budget(Base):
    """Monthly spending limit for one category (applies every calendar month)."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", name="uq_budgets_category_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    category: Mapped["Category"] = relationship(back_populates="budget")
