from pathlib import Path
import json


def detect_project_type(repository_path: str) -> str:
    root = Path(repository_path)

    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid repository directory.")

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

    # Node.js
    if (root / "package.json").is_file():
        return "node"

    # Java - Maven
    if (root / "pom.xml").is_file():
        return "maven"

    # Java - Gradle
    if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        return "gradle"

    raise ValueError("Unsupported project type.")


def generate_dockerfile(repository_path: str) -> str:
    root = Path(repository_path)

    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid repository directory.")

    if (root / "Dockerfile").is_file():
        return "Dockerfile already exists."

    project_type = detect_project_type(repository_path)

    # ---------------- PYTHON ----------------
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

    # ---------------- NODE ----------------
    elif project_type == "node":

        package_file = root / "package.json"

        try:
            package_data = json.loads(
                package_file.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
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

    # ---------------- MAVEN ----------------
    elif project_type == "maven":

        dockerfile_content = """FROM maven:3.9-eclipse-temurin-21

WORKDIR /app

COPY . .

RUN mvn package -DskipTests

EXPOSE 8080

CMD ["sh", "-c", "java -jar target/*.jar"]
"""

    # ---------------- GRADLE ----------------
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

    dockerfile_path = root / "Dockerfile"

    dockerfile_path.write_text(
        dockerfile_content,
        encoding="utf-8",
    )

    return f"Dockerfile generated for {project_type} project."
