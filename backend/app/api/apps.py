
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.application import Application


router = APIRouter(prefix="/api/v1/apps", tags=["apps"])


REPO_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


class DeployRequest(BaseModel):
    url: str
    branch: str = "main"

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        value = value.strip()

        if not REPO_RE.fullmatch(value):
            raise ValueError("Enter a valid GitHub repository URL")

        return value

    @field_validator("branch")
    @classmethod
    def valid_branch(cls, value: str) -> str:
        value = value.strip()

        if not re.fullmatch(r"[A-Za-z0-9_./-]+", value) or ".." in value:
            raise ValueError("Invalid branch name")

        return value


def serialize_app(app: Application):
    """Convert a database application into the frontend response format."""

    return {
        "id": app.id,
        "owner": app.owner,
        "repo": app.repo,
        "branch": app.branch,
        "status": app.status,
        "created_at": app.created_at.isoformat(),
        "deployment_id": app.deployment_id,
    }


@router.get("")
def list_apps(db: Session = Depends(get_db)):
    statement = select(Application).order_by(Application.id)

    apps = db.execute(statement).scalars().all()

    return [serialize_app(app) for app in apps]


@router.post("", status_code=202)
def create_app(
    body: DeployRequest,
    db: Session = Depends(get_db),
):
    match = REPO_RE.fullmatch(body.url.strip())

    owner, repo = match.group(1), match.group(2)

    # Check whether this repository is already registered
    statement = select(Application).where(
        Application.owner == owner,
        Application.repo == repo,
    )

    existing_app = db.execute(statement).scalar_one_or_none()

    if existing_app:
        raise HTTPException(
            status_code=409,
            detail="This repository is already registered",
        )

    # Create a new database application
    new_app = Application(
        owner=owner,
        repo=repo,
        branch=body.branch,
        status="QUEUED",
        deployment_id=secrets.token_hex(4),
    )

    try:
        db.add(new_app)
        db.commit()
        db.refresh(new_app)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="This repository is already registered",
        )

    return serialize_app(new_app)


@router.get("/{app_id}")
def get_app(
    app_id: int,
    db: Session = Depends(get_db),
):
    statement = select(Application).where(
        Application.id == app_id
    )

    app = db.execute(statement).scalar_one_or_none()

    if app is None:
        raise HTTPException(
            status_code=404,
            detail="App not found",
        )

    return serialize_app(app)
