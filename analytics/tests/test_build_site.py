"""build_site.py 완료 기준: 공용 고정 데이터 정답과 일치, 빈 raw-root 성공, CLI 종료 코드."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.helpers import ANALYTICS, CODE_VERSION, FIXTURES, GENERATED_AT, REPO, diff_sites, read_site

import build_site


def test_fixture_matches_reference_site_data(tmp_path):
    out = tmp_path / "site"
    build_site.build_site(
        FIXTURES / "raw-root", out, "2026-10-24T12:00:00", FIXTURES / "seeds", CODE_VERSION,
        generated_at=GENERATED_AT, work_dir=tmp_path / "work",
    )
    assert diff_sites(read_site(out), read_site(FIXTURES / "site" / "data")) == []


def test_fixture_scenarios_from_readme(tmp_path):
    """fixtures/README.md 시나리오 표의 핵심 기대값을 직접 확인한다 (정답 JSON 이 바뀌어도 의미를 지키기 위함)."""
    out = tmp_path / "site"
    files = build_site.build_site(
        FIXTURES / "raw-root", out, "2026-10-24T12:00:00", FIXTURES / "seeds", CODE_VERSION,
        generated_at=GENERATED_AT, work_dir=tmp_path / "work",
    )
    top = files["trends/all.json"]
    assert top[0] == {
        "id": "keyword-인공지능", "keyword": "인공지능", "category": "IT/과학", "score": 3.4,
        "mention_count": 4, "rank": 1, "changeType": "up", "changeValue": 3,
    }
    by_keyword = {item["keyword"]: item for item in top}
    assert by_keyword["반도체"]["score"] == 2.8 and by_keyword["반도체"]["changeValue"] == 2
    assert by_keyword["증시"]["changeType"] == "same"
    assert "보안" not in by_keyword and "속보" not in by_keyword
    stats = files["stats/all.json"]
    assert (stats["analyzedArticles"], stats["trackedKeywords"]) == (6, 6)
    assert stats["risingKeyword"]["keyword"] == "인공지능"
    assert stats["fallingKeyword"] == {"keyword": "환율", "mentionCount": 1, "changeAmount": -2}
    assert files["meta.json"]["freshness"] == "ok" and files["meta.json"]["freshnessHours"] == 2.66
    every_title = str(files)
    assert "다시 수집된" not in every_title  # 다른 실행의 같은 URL 은 먼저 수집된 행만
    assert "고정 기사 17" not in every_title  # as_of 이후 발행


@pytest.mark.parametrize("layout", ["no-raw-dir", "empty-raw-dirs"])
def test_empty_raw_root_succeeds_with_down_freshness(tmp_path, layout):
    raw_root = tmp_path / "raw-root"
    raw_root.mkdir()
    if layout == "empty-raw-dirs":
        (raw_root / "raw" / "articles").mkdir(parents=True)
        (raw_root / "raw" / "runs").mkdir(parents=True)
    out = tmp_path / "site"
    files = build_site.build_site(
        raw_root, out, "2026-10-24T12:00:00", ANALYTICS / "seeds", "local",
        generated_at=GENERATED_AT, work_dir=tmp_path / "work",
    )
    meta = files["meta.json"]
    assert meta["freshness"] == "down"
    assert meta["lastRun"] is None and meta["lastSuccessfulRunAt"] is None and meta["freshnessHours"] is None
    assert meta["counts"] == {"articles30d": 0, "keywords30d": 0, "runs7d": 0}
    assert files["trends/all.json"] == [] and files["categories.json"] == []
    assert files["keywords/index.json"]["keywords"] == []
    assert files["runs/recent.json"]["runs"] == []
    assert sorted(files) == [
        "categories.json", "keywords/index.json", "meta.json", "runs/recent.json",
        "stats/all.json", "trends/all.json", "trends/popular.json", "trends/surging/all.json",
    ]


def test_cli_matches_fixture_and_exit_code(tmp_path):
    out = tmp_path / "site"
    result = subprocess.run(
        [
            sys.executable, str(ANALYTICS / "build_site.py"),
            "--raw-root", str(FIXTURES / "raw-root"), "--seeds-dir", str(FIXTURES / "seeds"),
            "--as-of", "2026-10-24T12:00:00", "--out", str(out), "--code-version", CODE_VERSION,
            "--work-dir", str(tmp_path / "work"),
        ],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "freshness=ok" in result.stdout
    assert diff_sites(read_site(out), read_site(FIXTURES / "site" / "data")) == []
    contract = subprocess.run(
        [sys.executable, "contracts/validate.py", "--site-dir", str(out)], cwd=REPO, capture_output=True, text=True,
    )
    assert contract.returncode == 0, contract.stdout


def test_cli_rejects_bad_as_of(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ANALYTICS / "build_site.py"), "--raw-root", str(FIXTURES / "raw-root"),
         "--as-of", "2026-10-24 12:00", "--out", str(tmp_path / "site")],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "YYYY-MM-DDTHH:MM:SS" in result.stderr


def test_out_dir_that_is_not_site_output_is_not_deleted(tmp_path):
    out = tmp_path / "precious"
    out.mkdir()
    (out / "keep.txt").write_text("do not delete", encoding="utf-8")
    with pytest.raises(RuntimeError, match="정적 JSON 산출물"):
        build_site.build_site(
            FIXTURES / "raw-root", out, "2026-10-24T12:00:00", FIXTURES / "seeds", CODE_VERSION,
            generated_at=GENERATED_AT, work_dir=tmp_path / "work",
        )
    assert (out / "keep.txt").read_text(encoding="utf-8") == "do not delete"
