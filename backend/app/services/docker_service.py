
import docker
from docker.errors import (
    DockerException,
    BuildError,
    APIError,
    NotFound,
)


def get_docker_client():
    """Connect to Docker Engine."""
    try:
        client = docker.from_env()
        client.ping()
        return client

    except DockerException as error:
        raise RuntimeError(f"Could not connect to Docker: {error}")


def build_docker_image(
    repository_path: str,
    image_name: str,
    tag: str = "latest"
):
    """Build a Docker image from a cloned repository."""
    client = get_docker_client()

    try:
        image, build_logs = client.images.build(
            path=repository_path,
            tag=f"{image_name}:{tag}",
            rm=True
        )

        logs = [
            log["stream"].strip()
            for log in build_logs
            if "stream" in log
        ]

        return {
            "image_id": image.id,
            "image_name": image_name,
            "tag": tag,
            "status": "BUILT",
            "logs": logs
        }

    except BuildError as error:
        logs = [
            item.get("stream", "").strip()
            for item in error.build_log
            if item.get("stream")
        ]
        raise RuntimeError(
            f"Docker image build failed: {' '.join(logs)}"
        )

    except APIError as error:
        raise RuntimeError(f"Docker API error: {error}")


def start_docker_container(
    image_name: str,
    container_port: int,
    host_port: int,
    container_name: str
):
    """Start a container from a Docker image."""
    client = get_docker_client()

    try:
        container = client.containers.run(
            image=image_name,
            detach=True,
            name=container_name,
            ports={
                f"{container_port}/tcp": host_port
            }
        )

        container.reload()

        return {
            "container_id": container.id,
            "container_name": container.name,
            "status": container.status,
            "host_port": host_port,
            "container_port": container_port,
            "deployment_url": f"http://localhost:{host_port}"
        }

    except APIError as error:
        raise RuntimeError(f"Could not start container: {error}")


def stop_docker_container(container_id: str):
    """Stop a running container."""
    client = get_docker_client()

    try:
        container = client.containers.get(container_id)
        container.stop()

        return {
            "container_id": container.id,
            "status": "STOPPED"
        }

    except NotFound:
        raise RuntimeError("Container not found.")

    except APIError as error:
        raise RuntimeError(f"Could not stop container: {error}")


def restart_docker_container(container_id: str):
    """Restart a container."""
    client = get_docker_client()

    try:
        container = client.containers.get(container_id)
        container.restart()
        container.reload()

        return {
            "container_id": container.id,
            "status": container.status
        }

    except NotFound:
        raise RuntimeError("Container not found.")

    except APIError as error:
        raise RuntimeError(f"Could not restart container: {error}")



def get_container_status(container_id: str):
    """Get the current status and state details of a container."""
    client = get_docker_client()

    try:
        container = client.containers.get(container_id)
        container.reload()

        state = container.attrs.get("State", {})

        return {
            "container_id": container.id,
            "container_name": container.name,
            "status": container.status,
            "exit_code": state.get("ExitCode"),
            "error": state.get("Error"),
            "oom_killed": state.get("OOMKilled", False),
            "finished_at": state.get("FinishedAt"),
        }

    except NotFound:
        raise RuntimeError("Container not found.")

    except APIError as error:
        raise RuntimeError(
            f"Could not get container status: {error}"
        )


def get_container_logs(container_id: str):
    """Retrieve container logs."""
    client = get_docker_client()

    try:
        container = client.containers.get(container_id)

        logs = container.logs(
            stdout=True,
            stderr=True,
            tail=100
        ).decode("utf-8", errors="replace")

        return {
            "container_id": container.id,
            "logs": logs
        }

    except NotFound:
        raise RuntimeError("Container not found.")

    except APIError as error:
        raise RuntimeError(f"Could not retrieve logs: {error}")
    