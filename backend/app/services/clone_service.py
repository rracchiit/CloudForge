
import asyncio
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from app.services.github_service import (
    get_repository,
    get_branches as get_repository_branches,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_DIR = PROJECT_ROOT / "workspace"


def run_git_clone(clone_url: str, branch: str, destination: Path):
    """Run Git synchronously in a worker thread."""

    return subprocess.run(
        [
            "git",
            "clone",
            "--depth", "1",
            "--single-branch",
            "--branch", branch,
            clone_url,
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


async def clone_repository(owner: str, repo: str, branch: str):
    """Clone a public GitHub repository into CloudForge's workspace."""

    print("🔥 CLONE SERVICE STARTED", flush=True)

    # 1. Verify repository exists and is public
    repository = await get_repository(owner, repo)

    if repository.get("private"):
        raise ValueError("Only public repositories are supported.")

    # 2. Verify requested branch exists
    branches = await get_repository_branches(owner, repo)

    available_branches = [
        item["name"] for item in branches
    ]

    if branch not in available_branches:
        raise ValueError(
            f"Branch '{branch}' does not exist in this repository."
        )

    print("✅ REPOSITORY AND BRANCH VERIFIED", flush=True)

    # 3. Create unique destination
    clone_id = str(uuid4())
    destination = WORKSPACE_DIR / clone_id

    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    clone_url = f"https://github.com/{owner}/{repo}.git"

    try:
        # 4. Run Git outside the async event loop
        result = await asyncio.to_thread(
            run_git_clone,
            clone_url,
            branch,
            destination,
        )

        # 5. Check Git result
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"Git exited with code {result.returncode}"
            )

        print("✅ GIT CLONE COMPLETED", flush=True)

        return {
            "clone_id": clone_id,
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "path": str(destination),
            "status": "CLONED",
        }

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            "Repository cloning exceeded the 300-second limit."
        )

    except Exception:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)

        raise
