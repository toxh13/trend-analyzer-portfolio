"""build_pages.sh 테스트: build_site 는 stub, 프론트는 npm build 만 흉내 내는 작은 패키지."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, run_script

STUB = Path(__file__).parent / "stubs" / "build_site_stub.py"


@pytest.fixture
def fake_frontend(tmp_path: Path) -> Path:
    path = tmp_path / "frontend"
    path.mkdir()
    # 받은 빌드 변수를 index.html 에 남긴다. 실제 빌드처럼 public/data 같은 낡은 data/ 가 섞여 있어도 덮어써야 함
    script = (
        "mkdir -p build/data && echo stale > build/data/old.json && "
        'echo "$REACT_APP_DATA_MODE $PUBLIC_URL" > build/index.html'
    )
    (path / "package.json").write_text(json.dumps({"name": "fake", "version": "0.0.0", "scripts": {"build": script}}))
    return path


@pytest.fixture
def build(tmp_path: Path, fake_frontend: Path):
    args_file = tmp_path / "args.json"

    def run(**env: str):
        result = run_script(
            "build_pages.sh",
            str(REPO_ROOT / "fixtures" / "raw-root"),
            str(tmp_path / "_site"),
            cwd=tmp_path,
            env={"BUILD_SITE": str(STUB), "FRONTEND_DIR": str(fake_frontend), "PYTHON": sys.executable,
                 "STUB_ARGS_FILE": str(args_file), **env},
        )
        run.args = json.loads(args_file.read_text()) if args_file.exists() else None
        return result

    return run


def test_정적_JSON과_static_빌드를_합쳐_배포_디렉터리_생성(build, tmp_path: Path):
    result = build(SEEDS_DIR="fixtures/seeds", AS_OF="2026-10-24T12:00:00", CODE_VERSION="abc")

    assert result.returncode == 0, result.stderr + result.stdout
    site = tmp_path / "_site"
    assert (site / "index.html").read_text().strip() == "static /trend-analyzer-portfolio"
    assert (site / "data" / "meta.json").exists()
    assert not (site / "data" / "old.json").exists()
    expected = {p.relative_to(REPO_ROOT / "fixtures/site/data") for p in (REPO_ROOT / "fixtures/site/data").rglob("*.json")}
    assert {p.relative_to(site / "data") for p in (site / "data").rglob("*.json")} == expected
    assert build.args[build.args.index("--seeds-dir") + 1] == "fixtures/seeds"
    assert build.args[build.args.index("--as-of") + 1] == "2026-10-24T12:00:00"
    assert build.args[build.args.index("--code-version") + 1] == "abc"
    assert build.args[build.args.index("--raw-root") + 1] == str(REPO_ROOT / "fixtures" / "raw-root")


def test_선택_인자는_비우면_넘기지_않음(build):
    assert build().returncode == 0
    assert "--seeds-dir" not in build.args and "--as-of" not in build.args


def test_build_site가_실패하면_배포_디렉터리를_만들지_않음(build, tmp_path: Path):
    result = build(STUB_FAIL="1")

    assert result.returncode == 1
    assert not (tmp_path / "_site").exists()


def test_계약_위반이면_배포_디렉터리를_만들지_않음(build, tmp_path: Path):
    result = build(STUB_BREAK_CONTRACT="1")

    assert result.returncode == 1
    assert "meta.json" in result.stdout
    assert not (tmp_path / "_site").exists()
