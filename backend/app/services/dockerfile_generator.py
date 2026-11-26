
from pathlib import Path
import ast
import json


def detect_project_type(repository_path: str) -> str:
    root = Path(repository_path)

    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid repository directory.")

    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__"}

    # Reject desktop GUI applications.
    for file in root.rglob("*.py"):
        if any(part in ignored for part in file.parts):
            continue

        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "tkinter" for alias in node.names):
                    raise ValueError(
                        "Tkinter desktop applications are not supported "
                        "for browser-based deployment."
                    )

            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "tkinter"
                    or node.module.startswith("tkinter.")
                ):
                    raise ValueError(
                        "Tkinter desktop applications are not supported "
                        "for browser-based deployment."
                    )

    # Node.js
    if (root / "package.json").is_file():
        return "node"

    # Python
    python_files = [
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "setup.py",
    ]

    if any((root / file).is_file() for file in python_files):
        return "python"

    if any(root.glob("*.py")):
        return "python"

    # Java
    if (root / "pom.xml").is_file():
        return "maven"

    if (
        (root / "build.gradle").is_file()
        or (root / "build.gradle.kts").is_file()
    ):
        return "gradle"

    raise ValueError("Unsupported project type.")


def validate_existing_dockerfile(repository_path: str) -> str:
    root = Path(repository_path)
    dockerfile = root / "Dockerfile"

    if not dockerfile.is_file():
        raise ValueError("Dockerfile not found.")

    try:
        content = dockerfile.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ValueError("Dockerfile cannot be read.")

    instructions = [
        line.strip().upper()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    has_from = any(line.startswith("FROM ") for line in instructions)
    has_startup = any(
        line.startswith("CMD ") or line.startswith("ENTRYPOINT ")
        for line in instructions
    )

    if not has_from:
        raise ValueError("Dockerfile must contain a FROM instruction.")

    if not has_startup:
        raise ValueError(
            "Dockerfile must contain a CMD or ENTRYPOINT instruction."
        )

    return "Existing Dockerfile validated."


def generate_dockerfile(repository_path: str) -> str:
    root = Path(repository_path)

    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid repository directory.")

    project_type = detect_project_type(repository_path)

    if (root / "Dockerfile").is_file():
        return validate_existing_dockerfile(repository_path)

    if project_type == "python":
        if (root / "requirements.txt").is_file():
            dependency_install = """
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
"""
        else:
            dependency_install = ""

        if (root / "main.py").is_file():
            entrypoint = "main.py"
        elif (root / "app.py").is_file():
            entrypoint = "app.py"
        else:
            raise ValueError(
                "Python entrypoint not found. Expected main.py or app.py."
            )

        dockerfile_content = f"""FROM python:3.12-slim

WORKDIR /app

{dependency_install}
COPY . .

EXPOSE 8000

CMD ["python", "{entrypoint}"]
"""

    elif project_type == "node":
        try:
            package_data = json.loads(
                (root / "package.json").read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            raise ValueError("Invalid package.json.")

        scripts = package_data.get("scripts", {})

        if "start" in scripts:
            command = 'CMD ["npm", "start"]'
        elif (root / "index.js").is_file():
            command = 'CMD ["node", "index.js"]'
        elif (root / "server.js").is_file():
            command = 'CMD ["node", "server.js"]'
        else:
            raise ValueError(
                "Node entrypoint not found. Add a start script "
                "or index.js/server.js."
            )

        dockerfile_content = f"""FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

{command}
"""

    elif project_type == "maven":
        dockerfile_content = """FROM maven:3.9-eclipse-temurin-21

WORKDIR /app

COPY . .

RUN mvn package -DskipTests

EXPOSE 8080

CMD ["sh", "-c", "java -jar target/*.jar"]
"""

    elif project_type == "gradle":
        dockerfile_content = """FROM gradle:8.10-jdk21

WORKDIR /app

COPY . .

RUN gradle build -x test

EXPOSE 8080

CMD ["sh", "-c", "java -jar build/libs/*.jar"]
"""

    else:
        raise ValueError("Unsupported project type.")

    (root / "Dockerfile").write_text(
        dockerfile_content,
        encoding="utf-8",
    )

    return f"Dockerfile generated for {project_type} project."
