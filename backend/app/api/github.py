import logging
import os
import shutil
import stat
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.clone import Clone
from app.services.github_service import get_repository, get_branches
from app.services.clone_service import clone_repository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/github",
    tags=["GitHub"],
)


def handle_remove_readonly(func, path, exc_info):
    """Handle read-only files when deleting directories on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


# =============================
# Request Schemas
# =============================

class CloneRequest(BaseModel):
    owner: str = Field(
        ...,
        min_length=1,
        max_length=39,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$",
    )

    repo: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )

    branch: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )


# =============================
# Get Repository Details
# =============================

@router.get("/repos/{owner}/{repo}")
async def get_github_repository(owner: str, repo: str):
    try:
        return await get_repository(owner, repo)

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Could not fetch GitHub repository.",
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to GitHub.",
        )


# =============================
# Get Repository Branches
# =============================

@router.get("/repos/{owner}/{repo}/branches")
async def get_github_branches(owner: str, repo: str):
    try:
        return await get_branches(owner, repo)

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Could not fetch repository branches.",
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to GitHub.",
        )


# =============================
# Get All Cloned Repositories
# =============================

@router.get("/clones")
async def get_all_clones(
    db: Session = Depends(get_db),
):
    try:
        clones = (
            db.query(Clone)
            .order_by(Clone.created_at.desc())
            .all()
        )

        return [
            {
                "clone_id": clone.id,
                "owner": clone.owner,
                "repo": clone.repo,
                "branch": clone.branch,
                "github_url": clone.github_url,
                "local_path": clone.local_path,
                "status": clone.status,
                "created_at": clone.created_at,
            }
            for clone in clones
        ]

    except Exception:
        logger.exception("Failed to retrieve cloned repositories")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve cloned repositories.",
        )


# =============================
# Clone GitHub Repository
# =============================

@router.post("/clone", status_code=201)
async def clone_github_repository(
    body: CloneRequest,
    db: Session = Depends(get_db),
):
    logger.info("GitHub clone endpoint hit")

    try:
        # Step 1: Clone repository
        result = await clone_repository(
            owner=body.owner,
            repo=body.repo,
            branch=body.branch,
        )

        # Step 2: Create database record
        clone_record = Clone(
            id=result["clone_id"],
            owner=result["owner"],
            repo=result["repo"],
            branch=result["branch"],
            github_url=(
                f"https://github.com/"
                f"{result['owner']}/{result['repo']}"
            ),
            local_path=result["path"],
            status=result["status"],
        )

        # Step 3: Save record in PostgreSQL
        db.add(clone_record)
        db.commit()
        db.refresh(clone_record)

        logger.info("Clone successfully saved to database")

        # Step 4: Return clone information
        return {
            **result,
            "database_saved": True,
        }

    except httpx.HTTPStatusError as e:
        db.rollback()
        logger.exception("GitHub API request failed")

        raise HTTPException(
            status_code=e.response.status_code,
            detail="Could not access the GitHub repository.",
        )

    except httpx.RequestError:
        db.rollback()
        logger.exception("Could not connect to GitHub")

        raise HTTPException(
            status_code=503,
            detail="Could not connect to GitHub.",
        )

    except ValueError as e:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except TimeoutError:
        db.rollback()
        logger.exception("Repository cloning timed out")

        raise HTTPException(
            status_code=504,
            detail="Repository cloning timed out.",
        )

    except RuntimeError as e:
        db.rollback()
        logger.exception("GitHub repository cloning failed")

        raise HTTPException(
            status_code=400,
            detail=str(e) or "Cloning failed. Check backend logs.",
        )

    except Exception:
        db.rollback()
        logger.exception("Unexpected repository cloning error")

        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while cloning.",
        )


# =============================
# Get Clone by ID
# =============================

@router.get("/clones/{clone_id}")
async def get_clone_by_id(
    clone_id: str,
    db: Session = Depends(get_db),
):
    try:
        clone = (
            db.query(Clone)
            .filter(Clone.id == clone_id)
            .first()
        )

        if clone is None:
            raise HTTPException(
                status_code=404,
                detail="Clone not found.",
            )

        return {
            "clone_id": clone.id,
            "owner": clone.owner,
            "repo": clone.repo,
            "branch": clone.branch,
            "github_url": clone.github_url,
            "local_path": clone.local_path,
            "status": clone.status,
            "created_at": clone.created_at,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Failed to retrieve clone")

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve clone.",
        )


# =============================
# Delete Cloned Repository
# =============================

@router.delete("/clones/{clone_id}")
async def delete_clone(
    clone_id: str,
    db: Session = Depends(get_db),
):
    try:
        # Step 1: Find clone in database
        clone = (
            db.query(Clone)
            .filter(Clone.id == clone_id)
            .first()
        )

        if clone is None:
            raise HTTPException(
                status_code=404,
                detail="Clone not found.",
            )

        # Step 2: Define workspace directory
        project_root = Path(__file__).resolve().parents[3]
        workspace_dir = (project_root / "workspace").resolve()

        # Step 3: Resolve repository path
        clone_path = Path(clone.local_path).resolve()

        # Step 4: Ensure path is inside workspace
        try:
            clone_path.relative_to(workspace_dir)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid clone path. Deletion denied.",
            )

        if clone_path == workspace_dir:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the workspace directory.",
            )

        # Step 5: Delete local repository
        if clone_path.exists():
            if not clone_path.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail="Clone path is not a directory.",
                )

            shutil.rmtree(
                clone_path,
                onexc=handle_remove_readonly,
            )

        # Step 6: Delete database record
        db.delete(clone)
        db.commit()

        return {
            "message": "Clone deleted successfully.",
            "clone_id": clone_id,
            "local_files_deleted": True,
            "database_record_deleted": True,
        }

    except HTTPException:
        raise

    except OSError:
        db.rollback()
        logger.exception("Failed to delete local clone files")

        raise HTTPException(
            status_code=500,
            detail="Could not delete local repository files.",
        )

    except Exception:
        db.rollback()
        logger.exception("Failed to delete clone")

        raise HTTPException(
            status_code=500,
            detail="Could not delete clone.",
        )