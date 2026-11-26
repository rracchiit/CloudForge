from pathlib import Path

import pytest

from app.services.dockerfile_generator import (
    detect_project_type,
    generate_dockerfile,
)


def test_detect_python_project(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    assert detect_project_type(str(tmp_path)) == "python"


def test_detect_node_project(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"start": "node index.js"}}'
    )
    assert detect_project_type(str(tmp_path)) == "node"


def test_reject_unsupported_project(tmp_path):
    (tmp_path / "README.md").write_text("# Demo")

    with pytest.raises(ValueError, match="Unsupported project type"):
        detect_project_type(str(tmp_path))


def test_reject_tkinter_project(tmp_path):
    (tmp_path / "main.py").write_text(
        "import tkinter\n"
        "root = tkinter.Tk()\n"
    )

    with pytest.raises(ValueError, match="Tkinter"):
        detect_project_type(str(tmp_path))


def test_validate_existing_dockerfile(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY . .\n"
        'CMD ["python", "main.py"]\n'
    )

    assert generate_dockerfile(str(tmp_path)) == (
        "Existing Dockerfile validated."
    )


def test_reject_dockerfile_without_startup_command(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
    )

    with pytest.raises(ValueError, match="CMD or ENTRYPOINT"):
        generate_dockerfile(str(tmp_path))


def test_generate_python_dockerfile(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")

    result = generate_dockerfile(str(tmp_path))
    content = (tmp_path / "Dockerfile").read_text()

    assert result == "Dockerfile generated for python project."
    assert 'CMD ["python", "main.py"]' in content
    assert "EXPOSE 8000" in content


def test_reject_python_project_without_entrypoint(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests\n")

    with pytest.raises(ValueError, match="Python entrypoint"):
        generate_dockerfile(str(tmp_path))
