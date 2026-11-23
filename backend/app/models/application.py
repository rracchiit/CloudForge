
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )

    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repo: Mapped[str] = mapped_column(String(100), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), default="main")
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    deployment_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    project = relationship("Project", back_populates="applications")
    deployments = relationship(
        "Deployment",
        back_populates="application",
        cascade="all, delete-orphan",
    )
