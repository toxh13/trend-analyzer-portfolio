"""품질 게이트(DESIGN 5.2): 원천이 계약·대사식을 어기면 dbt build 가 실패해 배포를 막는지 확인한다."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.helpers import FIXTURES, GENERATED_AT

import build_site

R3_RUN = "raw/runs/dt=2026-10-24/33333333-3333-4333-8333-333333333333.json"
R3_ARTICLES = "raw/articles/dt=2026-10-24/33333333-3333-4333-8333-333333333333.jsonl"


@pytest.fixture
def workspace(tmp_path):
    raw_root = tmp_path / "raw-root"
    seeds = tmp_path / "seeds"
    shutil.copytree(FIXTURES / "raw-root", raw_root)
    shutil.copytree(FIXTURES / "seeds", seeds)
    return tmp_path, raw_root, seeds


def build(tmp_path: Path, raw_root: Path, seeds: Path, as_of="2026-10-24T12:00:00", strict=False):
    return build_site.build_site(
        raw_root, tmp_path / "site", as_of, seeds, "test",
        generated_at=GENERATED_AT, work_dir=tmp_path / "work", strict_freshness=strict,
    )


def edit_json(path: Path, **changes):
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.update(changes)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def edit_first_article(path: Path, **changes):
    lines = path.read_text(encoding="utf-8").splitlines()
    doc = json.loads(lines[0])
    doc.update(changes)
    lines[0] = json.dumps(doc, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_written_count_must_match_jsonl_lines(workspace):
    tmp_path, raw_root, seeds = workspace
    edit_json(raw_root / R3_RUN, writtenCount=7, selectedCount=7, eligibleCount=7, crawlerOutputCount=7)
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds)


def test_reconciliation_flag_must_be_true_only_when_equations_hold(workspace):
    tmp_path, raw_root, seeds = workspace
    edit_json(raw_root / R3_RUN, droppedByLimitCount=3)  # eligible != selected + dropped 인데 reconciliationOk=true
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds)


def test_unknown_channel_is_rejected(workspace):
    tmp_path, raw_root, seeds = workspace
    edit_first_article(raw_root / R3_ARTICLES, channel="kakao")
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds)


def test_bad_published_at_format_is_rejected(workspace):
    tmp_path, raw_root, seeds = workspace
    edit_first_article(raw_root / R3_ARTICLES, publishedAt="2026-10-23 14:00")
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds)


def test_blank_category_is_rejected(workspace):
    tmp_path, raw_root, seeds = workspace
    edit_first_article(raw_root / R3_ARTICLES, category="   ")
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds)


def test_conflicting_alias_is_rejected(workspace):
    tmp_path, raw_root, seeds = workspace
    with (seeds / "keyword_aliases.csv").open("a", encoding="utf-8") as file:
        file.write("a.i,인공 지능 기술,2026-10-02,conflict\n")  # normalize("a.i") == normalize("AI") 인데 대표가 다름
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds)


def test_stale_data_is_published_as_down_but_strict_mode_fails(workspace):
    tmp_path, raw_root, seeds = workspace
    files = build(tmp_path, raw_root, seeds, as_of="2026-10-26T12:00:00")
    assert files["meta.json"]["freshness"] == "down"
    assert files["meta.json"]["freshnessHours"] == 50.66
    with pytest.raises(RuntimeError, match="dbt build 실패"):
        build(tmp_path, raw_root, seeds, as_of="2026-10-26T12:00:00", strict=True)


def test_stale_between_6_and_24_hours(workspace):
    tmp_path, raw_root, seeds = workspace
    files = build(tmp_path, raw_root, seeds, as_of="2026-10-24T20:00:00")
    assert files["meta.json"]["freshness"] == "stale"
