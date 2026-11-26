
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.application import Application
from app.models.clone import Clone
from app.models.deployment import Deployment

from app.services.docker_service import (
    build_docker_image,
    start_docker_container,
    stop_docker_container,
    restart_docker_container,
    get_container_status,
    get_container_logs,
)

from app.services.dockerfile_generator import generate_dockerfile


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/deployments",
    tags=["Deployments"],
)


class BuildRequest(BaseModel):
    application_id: int = Field(..., gt=0)


class StartRequest(BaseModel):
    host_port: int = Field(default=8001, ge=1, le=65535)
    container_port: int = Field(default=8000, ge=1, le=65535)


# --------------------------------------------------
# LIST ALL DEPLOYMENTS
# --------------------------------------------------

@router.get("/")
def list_deployments(db: Session = Depends(get_db)):
    deployments = (
        db.query(Deployment)
        .order_by(Deployment.created_at.desc())
        .all()
    )

    return [
        {
            "id": deployment.id,
            "application_id": deployment.application_id,
            "owner": deployment.application.owner,
            "repo": deployment.application.repo,
            "branch": deployment.application.branch,
            "status": deployment.status,
            "image_name": deployment.image_name,
            "container_id": deployment.container_id,
            "host_port": deployment.host_port,
            "container_port": deployment.container_port,
            "deployment_url": deployment.deployment_url,
            "created_at": deployment.created_at,
        }
        for deployment in deployments
    ]


# --------------------------------------------------
# BUILD APPLICATION
# --------------------------------------------------

@router.post("/build", status_code=201)
def build_application(
    body: BuildRequest,
    db: Session = Depends(get_db),
):
    application = (
        db.query(Application)
        .filter(Application.id == body.application_id)
        .first()
    )

    if application is None:
        raise HTTPException(404, "Application not found.")

    clone = (
        db.query(Clone)
        .filter(
            Clone.owner == application.owner,
            Clone.repo == application.repo,
            Clone.branch == application.branch,
            Clone.status == "CLONED",
        )
        .order_by(Clone.created_at.desc())
        .first()
    )

    if clone is None:
        raise HTTPException(404, "No matching cloned repository found.")

    project_root = Path(__file__).resolve().parents[3]
    workspace_dir = (project_root / "workspace").resolve()
    repository_path = Path(clone.local_path).resolve()

    try:
        repository_path.relative_to(workspace_dir)
    except ValueError:
        raise HTTPException(
            400,
            "Repository path is outside CloudForge workspace.",
        )

    if repository_path == workspace_dir or not repository_path.is_dir():
        raise HTTPException(400, "Invalid repository directory.")

    try:
        generation_result = generate_dockerfile(
            str(repository_path)
        )

    except ValueError as error:
        raise HTTPException(400, str(error))

    safe_name = re.sub(
        r"[^a-z0-9]+",
        "-",
        f"{application.owner}-{application.repo}".lower(),
    ).strip("-")

    image_name = f"cloudforge-{safe_name}-{application.id}"

    deployment = Deployment(
        application_id=application.id,
        status="BUILDING",
        image_name=image_name,
        logs=generation_result,
    )

    try:
        db.add(deployment)
        db.commit()
        db.refresh(deployment)

    except Exception:
        db.rollback()
        logger.exception("Could not create deployment record")
        raise HTTPException(500, "Could not create deployment record.")

    try:
        result = build_docker_image(
            repository_path=str(repository_path),
            image_name=image_name,
            tag="latest",
        )

        deployment.image_id = result["image_id"]
        deployment.status = "BUILT"
        deployment.logs = "\n".join([
            generation_result,
            *result["logs"],
        ])

        db.commit()
        db.refresh(deployment)

        return {
            "message": "Docker image built successfully.",
            "deployment_id": deployment.id,
            "application_id": application.id,
            "dockerfile": generation_result,
            "image_name": result["image_name"],
            "image_id": result["image_id"],
            "status": deployment.status,
            "logs": result["logs"],
        }

    except Exception:
        db.rollback()
        logger.exception("Docker image build failed")

        try:
            deployment.status = "FAILED"
            deployment.logs = (
                f"{generation_result}\n"
                "Docker image build failed. Check backend logs."
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not save failed deployment status")

        raise HTTPException(
            500,
            "Docker image build failed. Check backend logs.",
        )


# --------------------------------------------------
# START DEPLOYMENT
# --------------------------------------------------

@router.post("/{deployment_id}/start")
def start_deployment(
    deployment_id: int,
    body: StartRequest,
    db: Session = Depends(get_db),
):
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if deployment is None:
        raise HTTPException(404, "Deployment not found.")

    if not deployment.image_name:
        raise HTTPException(400, "Deployment has no Docker image.")

    if deployment.container_id:
        try:
            current = get_container_status(deployment.container_id)

            if current["status"] == "running":
                raise HTTPException(
                    409,
                    "This deployment is already running.",
                )

        except RuntimeError:
            deployment.container_id = None

    try:
        result = start_docker_container(
            image_name=f"{deployment.image_name}:latest",
            container_port=body.container_port,
            host_port=body.host_port,
            container_name=f"cloudforge-deployment-{deployment.id}",
        )

        deployment.container_id = result["container_id"]
        deployment.container_port = result["container_port"]
        deployment.host_port = result["host_port"]
        deployment.deployment_url = result["deployment_url"]
        deployment.status = "RUNNING"

        db.commit()
        db.refresh(deployment)

        return {
            "message": "Deployment started successfully.",
            "deployment_id": deployment.id,
            "container_id": deployment.container_id,
            "status": deployment.status,
            "deployment_url": deployment.deployment_url,
        }

    except RuntimeError as error:
        db.rollback()
        logger.exception("Could not start deployment")
        raise HTTPException(500, str(error))


# --------------------------------------------------
# STOP DEPLOYMENT
# --------------------------------------------------

@router.post("/{deployment_id}/stop")
def stop_deployment(
    deployment_id: int,
    db: Session = Depends(get_db),
):
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if deployment is None:
        raise HTTPException(404, "Deployment not found.")

    if not deployment.container_id:
        raise HTTPException(400, "Deployment has no container.")

    try:
        result = stop_docker_container(deployment.container_id)

        deployment.status = result["status"]
        db.commit()

        return {
            "message": "Deployment stopped.",
            "deployment_id": deployment.id,
            "status": deployment.status,
        }

    except RuntimeError as error:
        raise HTTPException(500, str(error))


# --------------------------------------------------
# RESTART DEPLOYMENT
# --------------------------------------------------

@router.post("/{deployment_id}/restart")
def restart_deployment(
    deployment_id: int,
    db: Session = Depends(get_db),
):
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if deployment is None:
        raise HTTPException(404, "Deployment not found.")

    if not deployment.container_id:
        raise HTTPException(400, "Deployment has no container.")

    try:
        result = restart_docker_container(deployment.container_id)

        deployment.status = result["status"].upper()
        db.commit()

        return {
            "message": "Deployment restarted.",
            "deployment_id": deployment.id,
            "status": deployment.status,
        }

    except RuntimeError as error:
        raise HTTPException(500, str(error))


# --------------------------------------------------
# DEPLOYMENT STATUS
# --------------------------------------------------


@router.get("/{deployment_id}/status")
def deployment_status(
    deployment_id: int,
    db: Session = Depends(get_db),
):
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if deployment is None:
        raise HTTPException(404, "Deployment not found.")

    if not deployment.container_id:
        return {
            "deployment_id": deployment.id,
            "status": deployment.status,
            "container_status": None,
        }

    try:
        result = get_container_status(deployment.container_id)

        deployment.status = result["status"].upper()
        db.commit()

        return {
            "deployment_id": deployment.id,
            "container_id": result["container_id"],
            "container_name": result["container_name"],
            "status": result["status"],
            "exit_code": result["exit_code"],
            "error": result["error"],
            "oom_killed": result["oom_killed"],
            "finished_at": result["finished_at"],
            "deployment_url": deployment.deployment_url,
        }

    except RuntimeError as error:
        if str(error) == "Container not found.":
            deployment.status = "MISSING"
            db.commit()

            return {
                "deployment_id": deployment.id,
                "status": "MISSING",
                "container_status": None,
                "message": "The Docker container no longer exists.",
            }

        raise HTTPException(500, str(error))


# --------------------------------------------------
# DEPLOYMENT LOGS
# --------------------------------------------------

@router.get("/{deployment_id}/logs")
def deployment_logs(
    deployment_id: int,
    db: Session = Depends(get_db),
):
    deployment = db.query(Deployment).filter(
        Deployment.id == deployment_id
    ).first()

    if deployment is None:
        raise HTTPException(404, "Deployment not found.")

    if not deployment.container_id:
        raise HTTPException(400, "Deployment has no container.")

    try:
        return get_container_logs(deployment.container_id)

    except RuntimeError as error:
        raise HTTPException(500, str(error))
