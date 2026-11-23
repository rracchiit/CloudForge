
import httpx

from app.core.config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"


def get_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    return headers


async def get_repository(owner: str, repo: str):
    url = f"{GITHUB_API}/repos/{owner}/{repo}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers=get_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json()


async def get_branches(owner: str, repo: str):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/branches"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers=get_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json()
