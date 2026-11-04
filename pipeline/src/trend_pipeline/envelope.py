"""피드 요청/응답 한 건을 감싸는 원본 봉투(envelope). 한 번 쓰면 고치지 않는(write-once) 객체로 저장된다."""

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256

from trend_pipeline import __version__
from trend_pipeline.feeds import FeedSpec

# 저장된 봉투는 오래 남으므로 형식이 바뀌면 올린다. from_bytes는 다른 버전을 거부한다.
ENVELOPE_VERSION = 1
CRAWLER_VERSION = __version__


@dataclass(frozen=True)
class Envelope:
    envelope_version: int
    source: str
    feed: str
    request_url: str
    requested_at: datetime  # timezone 정보가 있는 UTC 시각
    crawler_version: str
    status: int  # 200 또는 304
    etag: str | None
    last_modified: str | None
    content_type: str | None
    body_sha256: str | None  # 304이면 None
    body: str | None  # 304이면 None


def _to_utc(value: datetime) -> datetime:
    # naive 시각은 어느 시간대인지 알 수 없어 기록이 틀어지므로 거부한다
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"timezone 정보가 있는 datetime이 필요하다: {value!r}")
    return value.astimezone(timezone.utc)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    # HTTP 헤더 이름은 대소문자를 구분하지 않으므로 키 표기와 무관하게 찾는다
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def build_envelope(
    spec: FeedSpec, requested_at: datetime, status: int, headers: Mapping[str, str], body: str | None
) -> Envelope:
    """응답 한 건으로 봉투를 만든다. 200과 304만 받고, 304는 본문 없이 기록한다."""
    if status == 200:
        if body is None:
            raise ValueError("status 200 응답에는 body가 필요하다")
        body_sha256 = sha256(body.encode("utf-8")).hexdigest()
    elif status == 304:
        # 서버가 빈 문자열 본문을 보내도 304는 본문이 없는 것으로 통일한다
        body, body_sha256 = None, None
    else:
        raise ValueError(f"봉투에 담을 수 있는 status는 200, 304뿐이다 (받은 값: {status})")

    return Envelope(
        envelope_version=ENVELOPE_VERSION,
        source=spec.source,
        feed=spec.feed,
        request_url=spec.url,
        requested_at=_to_utc(requested_at),
        crawler_version=CRAWLER_VERSION,
        status=status,
        etag=_header(headers, "ETag"),
        last_modified=_header(headers, "Last-Modified"),
        content_type=_header(headers, "Content-Type"),
        body_sha256=body_sha256,
        body=body,
    )


def to_bytes(env: Envelope) -> bytes:
    """봉투를 UTF-8 JSON 바이트로 직렬화한다. 같은 봉투는 항상 같은 바이트가 된다."""
    payload = asdict(env)
    payload["requested_at"] = _to_utc(env.requested_at).isoformat()
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def from_bytes(data: bytes) -> Envelope:
    """저장된 봉투를 읽는다. 모르는 envelope_version은 잘못 읽는 것보다 낫도록 거부한다."""
    payload = json.loads(data.decode("utf-8"))
    version = payload.get("envelope_version")
    if version != ENVELOPE_VERSION:
        raise ValueError(f"지원하지 않는 envelope_version: {version!r} (지원: {ENVELOPE_VERSION})")
    payload["requested_at"] = _to_utc(datetime.fromisoformat(payload["requested_at"]))
    return Envelope(**payload)
