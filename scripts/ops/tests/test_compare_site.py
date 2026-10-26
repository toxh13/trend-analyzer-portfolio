from __future__ import annotations

import json
import shutil
from pathlib import Path

import compare_site
from conftest import REPO_ROOT

FIXTURE_SITE = REPO_ROOT / "fixtures" / "site" / "data"


def copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "actual"
    shutil.copytree(FIXTURE_SITE, target)
    return target


def edit(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_같으면_0_generatedAt은_무시(tmp_path: Path, capsys):
    actual = copy_fixture(tmp_path)
    edit(actual / "meta.json", lambda d: d.update(generatedAt="2030-01-01T00:00:00Z"))

    assert compare_site.main([str(FIXTURE_SITE), str(actual)]) == 0
    assert "differences=0" in capsys.readouterr().out


def test_값이_다르면_경로를_알려줌(tmp_path: Path, capsys):
    actual = copy_fixture(tmp_path)
    edit(actual / "meta.json", lambda d: d.update(freshness="down"))

    assert compare_site.main([str(FIXTURE_SITE), str(actual)]) == 1
    assert "meta.json: /freshness: 'ok' != 'down'" in capsys.readouterr().out


def test_파일이_빠지거나_남으면_실패(tmp_path: Path, capsys):
    actual = copy_fixture(tmp_path)
    (actual / "categories.json").unlink()
    (actual / "extra.json").write_text("{}")

    assert compare_site.main([str(FIXTURE_SITE), str(actual)]) == 1
    out = capsys.readouterr().out
    assert "categories.json: 없음" in out and "extra.json: 예상하지 못한 파일" in out


def test_정수와_실수는_값이_같으면_같음():
    assert compare_site.first_difference({"a": [1, 2.0]}, {"a": [1.0, 2]}) is None
    assert compare_site.first_difference({"a": [1]}, {"a": [1, 2]}) == "/a: 길이 1 != 2"
    assert compare_site.first_difference({"a": 1}, {"a": "1"}) == "/a: 타입 int != str"
    assert compare_site.first_difference({"a": 1}, {}) == "/a: 없음"
    assert compare_site.first_difference({}, {"b": 1}) == "/b: 예상하지 못한 키"


def test_무시할_키_지정(tmp_path: Path):
    actual = copy_fixture(tmp_path)
    edit(actual / "meta.json", lambda d: d.update(codeVersion="abc"))

    assert compare_site.main([str(FIXTURE_SITE), str(actual)]) == 1
    assert compare_site.main([str(FIXTURE_SITE), str(actual), "--ignore-key", "generatedAt", "--ignore-key", "codeVersion"]) == 0


def test_기준_디렉터리가_비면_실패(tmp_path: Path):
    (tmp_path / "empty").mkdir()
    assert compare_site.main([str(tmp_path / "empty"), str(FIXTURE_SITE)]) == 1
