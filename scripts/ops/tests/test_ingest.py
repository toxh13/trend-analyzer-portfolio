"""ingest.sh 테스트: batch_cli 는 stub, GitHub 원격은 로컬 bare 저장소."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, git, run_script

STUB = Path(__file__).parent / "stubs" / "batch_cli_stub.py"


@pytest.fixture
def ingest(tmp_path: Path, data_clone: Path):
    args_file = tmp_path / "args.json"

    def run(**env: str) -> subprocess.CompletedProcess:
        result = run_script(
            "ingest.sh",
            str(data_clone),
            cwd=tmp_path,
            env={"BATCH_CLI": str(STUB), "PYTHON": sys.executable, "STUB_ARGS_FILE": str(args_file),
                 "GITHUB_OUTPUT": str(tmp_path / "gh_output"), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
                 **env},
        )
        run.args = json.loads(args_file.read_text()) if args_file.exists() else None
        return result

    return run


def remote_subjects(remote: Path) -> list[str]:
    return git(remote, "log", "--format=%s", "data").splitlines()


def test_성공_수집은_커밋되고_0(ingest, data_clone: Path, remote: Path, tmp_path: Path):
    result = ingest(TRIGGER="schedule", MAX_ARTICLES="10", CODE_VERSION="abc123")

    assert result.returncode == 0, result.stderr + result.stdout
    assert ingest.args[ingest.args.index("--trigger") + 1] == "schedule"
    assert ingest.args[ingest.args.index("--max-articles") + 1] == "10"
    assert ingest.args[ingest.args.index("--code-version") + 1] == "abc123"
    assert ingest.args[ingest.args.index("--seen-urls") + 1] == str(data_clone / "state" / "seen_urls.txt")
    assert "--source-fixture" not in ingest.args
    subject = remote_subjects(remote)[0]
    assert subject.startswith("data: ") and subject.endswith(" SUCCESS written=2")
    output = (tmp_path / "gh_output").read_text()
    assert "outcome=SUCCESS" in output and "written=2" in output
    assert "**SUCCESS**" in (tmp_path / "summary").read_text()

    # 커밋된 원천 파일이 계약을 만족
    check = tmp_path / "check"
    git(tmp_path, "clone", "-q", "-b", "data", str(remote), str(check))
    validate = subprocess.run(
        [sys.executable, str(REPO_ROOT / "contracts" / "validate.py"), "--raw-root", str(check)],
        capture_output=True, text=True,
    )
    assert validate.returncode == 0, validate.stdout


def test_두번째_실행은_seen_urls로_이미_수집한_URL_제외(ingest, remote: Path, data_clone: Path):
    assert ingest().returncode == 0
    result = ingest(STUB_URLS="https://news.example.com/a,https://news.example.com/c")

    assert result.returncode == 0, result.stderr
    assert remote_subjects(remote)[0].endswith(" SUCCESS written=1")
    seen = git(remote, "show", "data:state/seen_urls.txt").splitlines()
    assert seen == ["https://news.example.com/a", "https://news.example.com/b"]  # 두번째 실행 직전 기준


def test_FAILURE도_run_JSON은_커밋하고_1(ingest, remote: Path):
    result = ingest(STUB_OUTCOME="FAILURE")

    assert result.returncode == 1
    assert remote_subjects(remote)[0].endswith(" FAILURE written=0")
    assert "::error::수집 실패" in result.stdout


def test_PARTIAL_FAILURE는_경고만(ingest, remote: Path):
    result = ingest(STUB_OUTCOME="PARTIAL_FAILURE")

    assert result.returncode == 0
    assert "::warning::" in result.stdout
    assert remote_subjects(remote)[0].endswith(" PARTIAL_FAILURE written=2")


def test_EMPTY는_run_JSON만_커밋(ingest, remote: Path):
    result = ingest(STUB_URLS="")

    assert result.returncode == 0
    assert remote_subjects(remote)[0].endswith(" EMPTY written=0")
    files = git(remote, "show", "--name-only", "--format=", "data")
    assert "raw/runs/" in files and "raw/articles/" not in files


def test_run_JSON_없이_죽으면_커밋하지_않고_1(ingest, remote: Path):
    result = ingest(STUB_CRASH="1")

    assert result.returncode == 1
    assert "run JSON 경로를 남기지 않았습니다" in result.stdout
    assert remote_subjects(remote) == ["data: 브랜치 초기화"]


def test_SOURCE_FIXTURE와_SKIP_COMMIT(ingest, remote: Path, data_clone: Path):
    result = ingest(SOURCE_FIXTURE="/tmp/fixture.json", SKIP_COMMIT="1")

    assert result.returncode == 0
    assert ingest.args[ingest.args.index("--source-fixture") + 1] == "/tmp/fixture.json"
    assert ingest.args[ingest.args.index("--trigger") + 1] == "local"
    assert "--max-articles" not in ingest.args
    assert remote_subjects(remote) == ["data: 브랜치 초기화"]
    assert list((data_clone / "raw" / "runs").glob("dt=*/*.json"))


def test_push가_실패하면_1(ingest, remote: Path):
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    result = ingest(COMMIT_RAW_RETRIES="0")

    assert result.returncode == 1


@pytest.mark.parametrize("value", ["0", "abc", "10; rm -rf /", "-1"])
def test_MAX_ARTICLES가_정수가_아니면_2(ingest, remote: Path, value: str):
    result = ingest(MAX_ARTICLES=value)

    assert result.returncode == 2
    assert ingest.args is None  # batch_cli 를 부르지 않음
    assert remote_subjects(remote) == ["data: 브랜치 초기화"]
