
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Deployment status
    status: Mapped[str] = mapped_column(
        String(30),
        default="QUEUED",
        nullable=False,
    )

    # Docker image information
    image_name: Mapped[str | None] = mapped_column(String(255))
    image_id: Mapped[str | None] = mapped_column(String(255))

    # Docker container information
    container_id: Mapped[str | None] = mapped_column(String(255))

    # Port configuration
    host_port: Mapped[int | None] = mapped_column(Integer)
    container_port: Mapped[int | None] = mapped_column(Integer)

    # Deployment information
    deployment_url: Mapped[str | None] = mapped_column(String(500))
    logs: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    application = relationship(
        "Application",
        back_populates="deployments",
    )
