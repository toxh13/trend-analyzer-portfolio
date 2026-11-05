import threading
from pathlib import Path

import pytest

from trend_pipeline import raw_store as raw_store_module
from trend_pipeline.raw_store import LocalRawStore, RawIntegrityError

KEY = "raw/dt=2026-11-04/source=yna/feed=politics/run=20261104T030000Z.json"


def test_put_if_absent_only_first_wins(tmp_path):
    s = LocalRawStore(tmp_path)
    assert s.put_if_absent("raw/a.json", b"1") is True
    assert s.put_if_absent("raw/a.json", b"2") is False
    assert s.get("raw/a.json") == b"1"


def test_exists_after_put(tmp_path):
    s = LocalRawStore(tmp_path)
    assert s.exists(KEY) is False
    s.put_if_absent(KEY, b"x")
    assert s.exists(KEY) is True


def test_get_missing_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalRawStore(tmp_path).get(KEY)


def test_concurrent_put_exactly_one_true(tmp_path):
    s = LocalRawStore(tmp_path)
    workers = 8
    payloads = [f"payload-{i}".encode() for i in range(workers)]
    barrier = threading.Barrier(workers)
    results: list[bool | None] = [None] * workers
    errors: list[BaseException] = []

    def work(i: int) -> None:
        try:
            barrier.wait(timeout=10)  # 모든 스레드가 동시에 출발
            results[i] = s.put_if_absent(KEY, payloads[i])
        except BaseException as exc:  # 스레드 안 예외는 메인 스레드에서 확인하려고 모아 둔다
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == []
    assert results.count(True) == 1
    assert results.count(False) == workers - 1
    winner = results.index(True)
    assert s.get(KEY) == payloads[winner]


def test_no_partial_file_visible(tmp_path, monkeypatch):
    s = LocalRawStore(tmp_path)

    def boom(fd):
        raise OSError("디스크 오류")

    monkeypatch.setattr("trend_pipeline.raw_store.os.fsync", boom)
    with pytest.raises(OSError):
        s.put_if_absent(KEY, b"data")
    monkeypatch.undo()

    assert s.exists(KEY) is False
    assert s.list_keys("") == []


def test_temp_file_removed_after_failed_write(tmp_path, monkeypatch):
    s = LocalRawStore(tmp_path)

    def boom(src, dst):
        raise OSError("링크 실패")

    monkeypatch.setattr("trend_pipeline.raw_store.os.link", boom)
    with pytest.raises(OSError):
        s.put_if_absent(KEY, b"data")
    monkeypatch.undo()

    assert list((tmp_path / ".tmp").iterdir()) == []


def test_temp_file_removed_after_success_and_after_loser(tmp_path):
    s = LocalRawStore(tmp_path)
    s.put_if_absent(KEY, b"1")
    s.put_if_absent(KEY, b"2")
    assert list((tmp_path / ".tmp").iterdir()) == []


def test_integrity_mismatch_raises(tmp_path, monkeypatch):
    s = LocalRawStore(tmp_path)
    # 쓴 뒤 다시 읽은 값이 입력과 다르면 조용히 넘어가지 않는다
    monkeypatch.setattr(LocalRawStore, "get", lambda self, key: b"corrupted")
    with pytest.raises(RawIntegrityError):
        s.put_if_absent(KEY, b"original")


def test_list_and_delete_prefix(tmp_path):
    s = LocalRawStore(tmp_path)
    day4 = [
        "raw/dt=2026-11-04/source=yna/feed=politics/run=20261104T030000Z.json",
        "raw/dt=2026-11-04/source=khan/feed=kh_world/run=20261104T030000Z.json",
    ]
    day5 = ["raw/dt=2026-11-05/source=yna/feed=politics/run=20261105T030000Z.json"]
    for key in day4 + day5:
        assert s.put_if_absent(key, b"x") is True

    assert s.list_keys("raw/dt=2026-11-04/") == sorted(day4)
    assert s.list_keys("raw/dt=2026-11-05/") == day5
    assert s.list_keys("raw/") == sorted(day4 + day5)
    assert s.list_keys("raw/dt=2026-12-") == []

    assert s.delete_prefix("raw/dt=2026-11-04/") == 2
    assert s.list_keys("") == day5
    # 비어 버린 디렉터리는 치우고, 남은 날짜와 루트는 건드리지 않는다
    assert not (tmp_path / "raw" / "dt=2026-11-04").exists()
    assert (tmp_path / "raw" / "dt=2026-11-05").is_dir()
    assert tmp_path.is_dir()
    assert s.delete_prefix("raw/dt=2026-11-04/") == 0


def test_delete_all_keeps_root_and_tmp(tmp_path):
    s = LocalRawStore(tmp_path)
    s.put_if_absent(KEY, b"x")
    assert s.delete_prefix("raw/") == 1
    assert tmp_path.is_dir()
    assert (tmp_path / ".tmp").is_dir()
    assert not (tmp_path / "raw").exists()


def test_tmp_never_listed_or_deleted(tmp_path):
    s = LocalRawStore(tmp_path)
    s.put_if_absent(KEY, b"x")
    stray = tmp_path / ".tmp" / "stray.part"
    stray.write_bytes(b"leftover")

    assert s.list_keys("") == [KEY]
    assert s.list_keys(".tmp") == []
    assert s.delete_prefix(".tmp") == 0
    assert stray.exists()


def test_delete_prefix_rejects_empty_prefix(tmp_path):
    s = LocalRawStore(tmp_path)
    s.put_if_absent(KEY, b"x")
    with pytest.raises(ValueError):
        s.delete_prefix("")
    assert s.exists(KEY)


def test_list_keys_does_not_read_folders_outside_the_prefix(tmp_path, monkeypatch):
    # 원본이 쌓여도 다른 날짜 폴더는 읽지 않는다
    s = LocalRawStore(tmp_path)
    s.put_if_absent("raw/dt=2026-11-04/source=yna/feed=politics/run=20261104T030000Z.json", b"x")
    s.put_if_absent("raw/dt=2026-11-05/source=yna/feed=politics/run=20261105T030000Z.json", b"x")
    scanned = []
    real_scandir = raw_store_module.os.scandir

    def spy_scandir(path):
        scanned.append(Path(path))
        return real_scandir(path)

    monkeypatch.setattr(raw_store_module.os, "scandir", spy_scandir)
    assert len(s.list_keys("raw/dt=2026-11-04/")) == 1
    assert not any("dt=2026-11-05" in part for path in scanned for part in path.parts)
    assert len(s.list_keys("raw/dt=2026-1")) == 2  # 폴더 이름 중간에서 끝나는 접두어도 그 아래까지 본다


def test_list_keys_returns_names_as_stored_not_aliases(tmp_path):
    # Windows는 대소문자와 끝의 '.'을 무시해 'RAW/'·'raw./'로도 같은 폴더가 열린다.
    # 그런 별칭 접두어로 키를 돌려주거나 지우면 안 된다(키는 디스크에 있는 이름 그대로다)
    s = LocalRawStore(tmp_path)
    s.put_if_absent(KEY, b"x")
    assert s.list_keys("RAW/") == []
    assert s.list_keys("raw./") == []
    assert s.delete_prefix("raw./") == 0
    assert s.exists(KEY)


@pytest.mark.parametrize("prefix", ["../", "/raw/", ".tmp/", "raw/../raw/", "raw//", "C:/", "raw\\dt"])
def test_list_keys_with_prefix_no_key_can_have_is_empty(tmp_path, prefix):
    # 올바른 키가 가질 수 없는 접두어는 루트 밖이나 임시 폴더를 돌지 않고 빈 목록이다
    s = LocalRawStore(tmp_path)
    s.put_if_absent(KEY, b"x")
    (tmp_path / ".tmp" / "stray.part").write_bytes(b"leftover")
    assert s.list_keys(prefix) == []


def test_list_keys_on_missing_root_is_empty(tmp_path):
    assert LocalRawStore(tmp_path / "does-not-exist").list_keys("") == []


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../x",
        "raw/../../x",
        "raw/./a.json",
        "/abs/a.json",
        "raw\\a.json",
        "C:/a.json",
        "C:a.json",
        "raw//a.json",
        "raw/",
        ".tmp/a.json",
    ],
)
def test_bad_keys_rejected_everywhere(tmp_path, bad):
    s = LocalRawStore(tmp_path)
    with pytest.raises(ValueError):
        s.put_if_absent(bad, b"x")
    with pytest.raises(ValueError):
        s.exists(bad)
    with pytest.raises(ValueError):
        s.get(bad)
    # 루트 밖으로 아무것도 만들어지지 않았다
    assert not (tmp_path.parent / "x").exists()
    assert list(tmp_path.iterdir()) == []


def test_key_that_is_a_directory_is_an_error_not_a_silent_false(tmp_path):
    s = LocalRawStore(tmp_path)
    s.put_if_absent("raw/a/b.json", b"x")
    # "raw/a"는 디렉터리다. 이미 있다고 False로 넘기면 호출자가 영영 못 쓴 줄 모르고 건너뛴다
    assert s.exists("raw/a") is False
    with pytest.raises(IsADirectoryError):
        s.put_if_absent("raw/a", b"y")
