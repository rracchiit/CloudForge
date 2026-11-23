
from pathlib import Path


def detect_project_type(repository_path: str) -> str:
    """
    Detect the project language using repository files.
    """

    root = Path(repository_path)

    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid repository directory.")

    # Python project detection
    python_files = [
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "setup.py",
    ]

    if any((root / filename).is_file() for filename in python_files):
        return "python"

    if any(root.glob("*.py")):
        return "python"

    # Node.js project detection
    if (root / "package.json").is_file():
        return "node"

    # Java project detection
    if (
        (root / "pom.xml").is_file()
        or (root / "build.gradle").is_file()
    ):
        return "java"

    raise ValueError("Unsupported project type.")


def generate_dockerfile(repository_path: str) -> str:
    """
    Generate a Dockerfile based on the detected project type.
    """

    root = Path(repository_path)
    project_type = detect_project_type(repository_path)

    if (root / "Dockerfile").exists():
        return "Dockerfile already exists."

    if project_type == "python":

        if (root / "requirements.txt").exists():
            dependency_install = (
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
            )
        else:
            dependency_install = ""

        dockerfile_content = f"""FROM python:3.12-slim

WORKDIR /app

{dependency_install}
COPY . .

CMD ["python", "app.py"]
"""

    elif project_type == "node":

        dockerfile_content = """FROM node:22-slim

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

CMD ["npm", "start"]
"""

    elif project_type == "java":

        dockerfile_content = """FROM maven:3.9-eclipse-temurin-21

WORKDIR /app

COPY . .

RUN mvn package -DskipTests

CMD ["sh", "-c", "java -jar target/*.jar"]
"""

    else:
        raise ValueError("Unsupported project type.")

    dockerfile_path = root / "Dockerfile"

    dockerfile_path.write_text(
        dockerfile_content,
        encoding="utf-8",
    )

    return f"Dockerfile generated for {project_type} project."
