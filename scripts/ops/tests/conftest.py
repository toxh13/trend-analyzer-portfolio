from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

OPS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = OPS_DIR.parents[1]
sys.path.insert(0, str(OPS_DIR))

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(cwd: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, env={**os.environ, **GIT_ENV}, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} 실패: {result.stderr}")
    return result.stdout.strip()


def run_script(script: str, *args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(OPS_DIR / script), *args],
        cwd=cwd,
        env={**os.environ, **GIT_ENV, "COMMIT_RAW_BACKOFF": "0", **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """GitHub 대신 쓰는 로컬 bare 저장소(네트워크 없음)."""
    path = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(path))
    return path


@pytest.fixture
def main_clone(tmp_path: Path, remote: Path) -> Path:
    """main 브랜치만 있는 작업 저장소. origin = remote."""
    path = tmp_path / "main"
    git(tmp_path, "init", "-q", "-b", "main", str(path))
    (path / "README.md").write_text("main\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "init")
    git(path, "remote", "add", "origin", str(remote))
    git(path, "push", "-q", "origin", "main")
    return path


@pytest.fixture
def data_clone(tmp_path: Path, main_clone: Path, remote: Path) -> Path:
    """init_data_branch.sh 로 만든 data 브랜치 체크아웃 (actions/checkout ref: data 에 해당)."""
    result = run_script("init_data_branch.sh", cwd=main_clone)
    assert result.returncode == 0, result.stderr
    path = tmp_path / "data"
    git(tmp_path, "clone", "-q", "-b", "data", str(remote), str(path))
    return path
