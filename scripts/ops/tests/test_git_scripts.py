"""init_data_branch.sh·commit_raw.sh 테스트. GitHub 원격 대신 로컬 bare 저장소를 쓴다(네트워크 없음)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import git, run_script

RUN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def write_run(data: Path, run_id: str = RUN_ID, outcome: str = "SUCCESS", written: int = 2, dt: str = "2026-10-24"):
    articles = data / "raw" / "articles" / f"dt={dt}" / f"{run_id}.jsonl"
    articles.parent.mkdir(parents=True, exist_ok=True)
    articles.write_text("".join(json.dumps({"sourceUrl": f"https://x/{run_id}/{i}"}) + "\n" for i in range(written)))
    run = data / "raw" / "runs" / f"dt={dt}" / f"{run_id}.json"
    run.parent.mkdir(parents=True, exist_ok=True)
    run.write_text(json.dumps({"runId": run_id, "outcome": outcome, "writtenCount": written}))
    return run


# ---------- init_data_branch.sh ----------


def test_init_orphan_data_브랜치_생성(main_clone: Path, remote: Path):
    head_before = git(main_clone, "rev-parse", "HEAD")
    result = run_script("init_data_branch.sh", cwd=main_clone)

    assert result.returncode == 0, result.stderr
    files = git(remote, "ls-tree", "-r", "--name-only", "data").splitlines()
    assert files == ["README.md", "raw/articles/.gitkeep", "raw/runs/.gitkeep", "state/.gitkeep"]
    # 부모 없는 커밋(orphan) 하나
    assert git(remote, "rev-list", "--parents", "data") == git(remote, "rev-parse", "data")
    assert git(remote, "log", "-1", "--format=%s", "data") == "data: 브랜치 초기화"
    assert "원천 데이터 저장소" in git(remote, "show", "data:README.md")
    # 현재 작업 트리·브랜치는 그대로
    assert git(main_clone, "rev-parse", "HEAD") == head_before
    assert git(main_clone, "branch", "--show-current") == "main"
    assert git(main_clone, "status", "--porcelain") == ""


def test_init_이미_있으면_아무것도_안함(main_clone: Path, remote: Path):
    run_script("init_data_branch.sh", cwd=main_clone)
    first = git(remote, "rev-parse", "data")

    result = run_script("init_data_branch.sh", cwd=main_clone)

    assert result.returncode == 0
    assert "이미 있음" in result.stdout
    assert git(remote, "rev-parse", "data") == first


def test_init_dry_run은_push하지_않음(main_clone: Path, remote: Path):
    result = run_script("init_data_branch.sh", "--dry-run", cwd=main_clone)

    assert result.returncode == 0, result.stderr
    assert "[dry-run]" in result.stdout and "state/.gitkeep" in result.stdout
    assert git(remote, "branch", "--list", "data") == ""


def test_init_DATA_BRANCH로_이름_변경(main_clone: Path, remote: Path):
    result = run_script("init_data_branch.sh", cwd=main_clone, env={"DATA_BRANCH": "data-test"})
    assert result.returncode == 0, result.stderr
    assert git(remote, "branch", "--list", "data-test").strip() == "data-test"


# ---------- commit_raw.sh ----------


def test_commit_메시지와_push(data_clone: Path, remote: Path):
    run = write_run(data_clone, written=2)
    (data_clone / "state" / "seen_urls.txt").write_text("https://x/old\n")

    result = run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone)

    assert result.returncode == 0, result.stderr
    assert git(remote, "log", "-1", "--format=%s", "data") == f"data: {RUN_ID} SUCCESS written=2"
    changed = git(remote, "show", "--name-only", "--format=", "data").splitlines()
    assert sorted(changed) == [
        f"raw/articles/dt=2026-10-24/{RUN_ID}.jsonl",
        f"raw/runs/dt=2026-10-24/{RUN_ID}.json",
        "state/seen_urls.txt",
    ]


def test_commit_raw_밖의_파일은_커밋하지_않음(data_clone: Path, remote: Path):
    run = write_run(data_clone)
    (data_clone / "stray.txt").write_text("x")

    run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone)

    assert "stray.txt" not in git(remote, "ls-tree", "-r", "--name-only", "data")


def test_commit_바뀐_게_없으면_커밋하지_않음(data_clone: Path, remote: Path):
    run = write_run(data_clone)
    run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone)
    head = git(remote, "rev-parse", "data")

    result = run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone)

    assert result.returncode == 0
    assert "바뀐 파일 없음" in result.stdout
    assert git(remote, "rev-parse", "data") == head


def test_commit_다른_실행이_먼저_push하면_rebase_후_재시도(tmp_path: Path, data_clone: Path, remote: Path):
    # 다른 실행(예: backfill)이 먼저 push 한 상황
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "data", str(remote), str(other))
    other_run = write_run(other, run_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", written=1)
    (other / "state" / "seen_urls.txt").write_text("https://x/from-other\n")
    assert run_script("commit_raw.sh", str(other), str(other_run), cwd=other).returncode == 0

    run = write_run(data_clone, written=3)
    (data_clone / "state" / "seen_urls.txt").write_text("https://x/from-me\n")
    result = run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone)

    assert result.returncode == 0, result.stderr
    assert "재시도 1/3" in result.stderr
    subjects = git(remote, "log", "--format=%s", "data").splitlines()
    assert subjects[:2] == [
        f"data: {RUN_ID} SUCCESS written=3",
        "data: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb SUCCESS written=1",
    ]
    # 선형 히스토리(merge commit 없음), 두 실행의 원천 파일 모두 존재
    assert git(remote, "rev-list", "--merges", "data") == ""
    files = git(remote, "ls-tree", "-r", "--name-only", "data")
    assert RUN_ID in files and "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" in files
    # seen_urls 충돌은 지금 올리는 쪽으로 해소
    assert git(remote, "show", "data:state/seen_urls.txt") == "https://x/from-me"


def test_commit_계속_거부되면_3회_재시도_후_실패(data_clone: Path, remote: Path):
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected >&2\nexit 1\n")
    hook.chmod(0o755)
    run = write_run(data_clone)

    result = run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone)

    assert result.returncode == 1
    assert result.stderr.count("rebase 후 재시도") == 3
    assert "3회 재시도 후 포기" in result.stderr


def test_commit_재시도_횟수_설정(data_clone: Path, remote: Path):
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    run = write_run(data_clone)

    result = run_script("commit_raw.sh", str(data_clone), str(run), cwd=data_clone, env={"COMMIT_RAW_RETRIES": "1"})

    assert result.returncode == 1
    assert result.stderr.count("rebase 후 재시도") == 1


def test_commit_인자가_없으면_2(tmp_path: Path):
    assert run_script("commit_raw.sh", cwd=tmp_path).returncode == 2


def test_commit_run_json이_깨졌으면_실패(data_clone: Path):
    bad = data_clone / "bad.json"
    bad.write_text("{}")
    result = run_script("commit_raw.sh", str(data_clone), str(bad), cwd=data_clone)
    assert result.returncode != 0
    assert git(data_clone, "log", "--format=%s") == "data: 브랜치 초기화"


def test_스크립트는_bash_문법_검사_통과():
    from conftest import OPS_DIR

    for script in sorted(OPS_DIR.glob("*.sh")):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script.name}: {result.stderr}"
