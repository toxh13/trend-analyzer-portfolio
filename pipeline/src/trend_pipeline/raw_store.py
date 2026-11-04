"""원본(raw) 봉투 저장소. 한 번 쓴 객체는 덮어쓰지 않는다(write-once).

로컬 디스크 구현(LocalRawStore)과 같은 인터페이스(RawStore)로 나중에 OCI Object Storage 구현을 붙인다.
"""

import hashlib
import os
import uuid
from pathlib import Path
from typing import Protocol

_TMP_DIR = ".tmp"  # 쓰는 중인 파일이 머무는 곳. 키 공간이 아니므로 목록·삭제 대상에서 항상 뺀다


class RawIntegrityError(Exception):
    """쓴 직후 다시 읽은 내용이 입력과 다르다(디스크 오류 등)."""


class RawStore(Protocol):
    def exists(self, key: str) -> bool:
        """해당 키의 객체가 있는가."""
        ...

    def put_if_absent(self, key: str, data: bytes) -> bool:
        """없을 때만 쓴다. 쓰면 True, 이미 있으면 False. 이미 있는 객체는 절대 덮어쓰지 않는다."""
        ...

    def get(self, key: str) -> bytes:
        """객체 내용. 없으면 FileNotFoundError."""
        ...

    def list_keys(self, prefix: str) -> list[str]:
        """prefix로 시작하는 키를 정렬해서 돌려준다(단순 문자열 접두어)."""
        ...

    def delete_prefix(self, prefix: str) -> int:
        """prefix로 시작하는 객체를 모두 지우고 지운 개수를 돌려준다."""
        ...


def _validate_key(key: str) -> None:
    # 키는 코드가 만들지만, 잘못된 키가 루트 밖으로 새거나 다른 키와 같은 파일을 가리키면 안 된다
    if not key:
        raise ValueError("키가 비어 있다")
    if key.startswith("/") or "\\" in key:
        raise ValueError(f"절대 경로이거나 역슬래시가 든 키는 쓸 수 없다: {key!r}")
    # ':'는 윈도우 드라이브 문자(C:)와 NTFS 대체 데이터 스트림(a:b)을 막으려고 거부한다
    if ":" in key:
        raise ValueError(f"':'가 든 키는 쓸 수 없다: {key!r}")
    parts = key.split("/")
    # 빈 조각('a//b', 끝 '/')과 '.'은 같은 파일에 다른 키 문자열이 붙는 별칭을 만든다
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"빈 조각, '.', '..' 조각이 든 키는 쓸 수 없다: {key!r}")
    if parts[0] == _TMP_DIR:
        raise ValueError(f"{_TMP_DIR}는 임시 파일 전용 디렉터리라 키로 쓸 수 없다: {key!r}")


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


class LocalRawStore:
    """로컬 디스크 저장소. 키(`raw/dt=.../x.json`)가 root 아래 상대 경로가 된다."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        _validate_key(key)
        return self._root / key

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def put_if_absent(self, key: str, data: bytes) -> bool:
        target = self._path(key)
        # 임시 파일은 root 안에 둔다. os.link는 같은 볼륨 안에서만 되기 때문이다
        tmp_dir = self._root / _TMP_DIR
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"{uuid.uuid4().hex}.part"
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                # 최종 경로는 완성된 내용으로만 나타난다. 이미 있으면 FileExistsError로 먼저 쓴 쪽이 이긴다
                os.link(tmp, target)
            except FileExistsError:
                if target.is_dir():
                    # 디렉터리 이름과 겹친 키. False로 넘기면 호출자가 '이미 수집했다'고 잘못 알고 건너뛴다
                    raise IsADirectoryError(f"디렉터리와 겹치는 키다: {key!r}") from None
                return False
        finally:
            tmp.unlink(missing_ok=True)

        if _sha256(self.get(key)) != _sha256(data):
            raise RawIntegrityError(f"쓴 뒤 다시 읽은 내용이 입력과 다르다: {key}")
        return True

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            directory = Path(dirpath)
            if directory == self._root and _TMP_DIR in dirnames:
                dirnames.remove(_TMP_DIR)  # 임시 디렉터리는 내려가지 않는다
            for name in filenames:
                key = (directory / name).relative_to(self._root).as_posix()
                if key.startswith(prefix):
                    keys.append(key)
        return sorted(keys)

    def delete_prefix(self, prefix: str) -> int:
        if not prefix:
            # 빈 접두어는 저장소 전체를 지운다. 실수로 넘어온 빈 문자열이 전부 지우지 않게 막는다
            raise ValueError("빈 접두어로는 지울 수 없다")
        deleted = 0
        for key in self.list_keys(prefix):
            path = self._root / key
            try:
                path.unlink()
            except FileNotFoundError:
                continue  # 목록을 뜬 뒤 다른 쪽이 먼저 지웠다
            deleted += 1
            self._remove_empty_parents(path.parent)
        return deleted

    def _remove_empty_parents(self, directory: Path) -> None:
        # 루트 바로 아래까지만 올라가며 비어 버린 디렉터리를 치운다(루트와 .tmp는 건드리지 않는다)
        while directory != self._root and self._root in directory.parents:
            try:
                directory.rmdir()
            except OSError:
                return  # 비어 있지 않다
            directory = directory.parent
