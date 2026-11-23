from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Clone(Base):
    __tablename__ = "clones"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repo: Mapped[str] = mapped_column(String(100), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)

    github_url: Mapped[str] = mapped_column(String(500), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    status: Mapped[str] = mapped_column(
        String(30),
        default="CLONED",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )