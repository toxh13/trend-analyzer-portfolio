from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import build_seen_urls
from conftest import REPO_ROOT


def write_articles(root: Path, dt: str, name: str, urls: list[str]) -> None:
    path = root / "raw" / "articles" / f"dt={dt}" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"sourceUrl": url}) + "\n" for url in urls), encoding="utf-8")


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_최근_7일과_경계일만_포함하고_정렬_중복제거(tmp_path: Path):
    write_articles(tmp_path, "2026-10-16", "old", ["https://x/old"])  # today-8: 제외
    write_articles(tmp_path, "2026-10-17", "edge", ["https://x/edge"])  # today-7: 포함(경계)
    write_articles(tmp_path, "2026-10-20", "a", ["https://x/b", "https://x/a"])
    write_articles(tmp_path, "2026-10-24", "b", ["https://x/a", " https://x/c "])
    write_articles(tmp_path, "2026-10-25", "future", ["https://x/future"])  # 미래: 제외

    code = build_seen_urls.main(["--data-dir", str(tmp_path), "--today", "2026-10-24"])

    assert code == 0
    assert read_lines(tmp_path / "state" / "seen_urls.txt") == [
        "https://x/a",
        "https://x/b",
        "https://x/c",
        "https://x/edge",
    ]


def test_dt_형식이_아니거나_jsonl이_아니면_무시(tmp_path: Path):
    write_articles(tmp_path, "2026-10-24", "ok", ["https://x/ok"])
    bad_dir = tmp_path / "raw" / "articles" / "dt=2026-13-40"
    bad_dir.mkdir(parents=True)
    (bad_dir / "x.jsonl").write_text(json.dumps({"sourceUrl": "https://x/bad-date"}) + "\n", encoding="utf-8")
    other = tmp_path / "raw" / "articles" / "misc"
    other.mkdir()
    (other / "x.jsonl").write_text(json.dumps({"sourceUrl": "https://x/misc"}) + "\n", encoding="utf-8")
    (tmp_path / "raw" / "articles" / "dt=2026-10-24" / "note.txt").write_text("https://x/txt\n", encoding="utf-8")

    build_seen_urls.main(["--data-dir", str(tmp_path), "--today", "2026-10-24"])

    assert read_lines(tmp_path / "state" / "seen_urls.txt") == ["https://x/ok"]


def test_깨진_줄은_경고하고_건너뜀(tmp_path: Path, capsys):
    path = tmp_path / "raw" / "articles" / "dt=2026-10-24" / "r.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"sourceUrl": "https://x/1"}\n\nnot-json\n{"title": "url 없음"}\n[1, 2]\n{"sourceUrl": ""}\n',
        encoding="utf-8",
    )

    build_seen_urls.main(["--data-dir", str(tmp_path), "--today", "2026-10-24"])

    assert read_lines(tmp_path / "state" / "seen_urls.txt") == ["https://x/1"]
    captured = capsys.readouterr()
    assert "skipped=4" in captured.out
    assert len(captured.err.splitlines()) == 4


def test_원천이_없으면_빈_파일(tmp_path: Path):
    output = tmp_path / "out" / "seen.txt"
    code = build_seen_urls.main(["--data-dir", str(tmp_path), "--output", str(output)])
    assert code == 0
    assert output.read_text(encoding="utf-8") == ""


def test_days_0이면_오늘만(tmp_path: Path):
    write_articles(tmp_path, "2026-10-23", "a", ["https://x/yesterday"])
    write_articles(tmp_path, "2026-10-24", "b", ["https://x/today"])
    build_seen_urls.main(["--data-dir", str(tmp_path), "--today", "2026-10-24", "--days", "0"])
    assert read_lines(tmp_path / "state" / "seen_urls.txt") == ["https://x/today"]


def test_공용_고정_데이터(tmp_path: Path):
    raw_root = REPO_ROOT / "fixtures" / "raw-root"
    expected = set()
    for path in raw_root.glob("raw/articles/dt=*/*.jsonl"):
        expected |= {json.loads(line)["sourceUrl"] for line in path.read_text(encoding="utf-8").splitlines()}
    output = tmp_path / "seen.txt"

    build_seen_urls.main(["--data-dir", str(raw_root), "--today", "2026-10-24", "--output", str(output)])

    lines = read_lines(output)
    assert lines == sorted(expected)
    assert len(lines) < 18  # 기사 18줄 중 R2·R3 의 같은 URL(기사 10)은 한 번만


def test_기본_today는_서울_날짜(monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # UTC 10/24 16:00 = 서울 10/25 01:00
            return datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(build_seen_urls, "datetime", FrozenDatetime)
    assert build_seen_urls.seoul_today() == date(2026, 10, 25)
