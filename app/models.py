"""ORM models.

The data model is intentionally small:

* ``Recipe``       – a recipe with free-text fields and a source link
* ``Tag``          – many-to-many with recipes
* ``Attachment``   – many-to-one with recipes (images, text files, anything else)
* ``RotationPlan`` – a saved calendar plan (fixed or random, weekly or monthly)
* ``RotationItem`` – ordered recipe candidates for a plan
* ``CalendarEntry``– one recipe assigned to one day; can be cooked/skipped
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Timezone-naive UTC timestamp (SQLite stores naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


recipe_tags = Table(
    "recipe_tags",
    Base.metadata,
    Column("recipe_id", Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(2048), default="")
    ingredients: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    tags: Mapped[list["Tag"]] = relationship(
        secondary=recipe_tags, back_populates="recipes", lazy="selectin", order_by="Tag.name"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Attachment.id",
    )

    @property
    def image_attachments(self) -> list["Attachment"]:
        return [a for a in self.attachments if a.kind == "image"]

    @property
    def text_attachments(self) -> list["Attachment"]:
        return [a for a in self.attachments if a.kind == "text"]

    @property
    def other_attachments(self) -> list["Attachment"]:
        return [a for a in self.attachments if a.kind == "other"]

    @property
    def search_blob(self) -> str:
        return " ".join(
            filter(None, [self.name, self.description, self.ingredients, self.instructions])
        ).lower()


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    recipes: Mapped[list[Recipe]] = relationship(secondary=recipe_tags, back_populates="tags")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(150), default="application/octet-stream")
    kind: Mapped[str] = mapped_column(String(20), default="other")  # image | text | other
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    recipe: Mapped[Recipe] = relationship(back_populates="attachments")


class RotationPlan(Base):
    __tablename__ = "rotation_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    mode: Mapped[str] = mapped_column(String(20), default="fixed")  # fixed | random
    interval: Mapped[str] = mapped_column(String(20), default="weekly")  # weekly | monthly
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    spacing: Mapped[int] = mapped_column(Integer, default=1)  # days between planned recipes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    items: Mapped[list["RotationItem"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="RotationItem.position",
        lazy="selectin",
    )
    entries: Mapped[list["CalendarEntry"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    @property
    def cycle_length(self) -> int:
        return 30 if self.interval == "monthly" else 7


class RotationItem(Base):
    __tablename__ = "rotation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("rotation_plans.id", ondelete="CASCADE"), index=True
    )
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[RotationPlan] = relationship(back_populates="items")
    recipe: Mapped[Recipe] = relationship(lazy="joined")


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"
    __table_args__ = (UniqueConstraint("plan_id", "entry_date", name="uq_entry_plan_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("rotation_plans.id", ondelete="CASCADE"), index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned | cooked | skipped
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    plan: Mapped[RotationPlan] = relationship(back_populates="entries")
    recipe: Mapped[Recipe | None] = relationship(lazy="joined")
