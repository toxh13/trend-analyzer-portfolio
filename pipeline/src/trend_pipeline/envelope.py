"""피드 요청/응답 한 건을 감싸는 원본 봉투(envelope). 한 번 쓰면 고치지 않는(write-once) 객체로 저장된다.

봉투는 받은 본문 바이트를 그대로 담는다(v2). 글자로 바꾸는(디코드) 일은 읽는 쪽(body_text)이 한다.
그래야 디코드 규칙이 바뀌어도 원본에서 다시 처리할 수 있고, body_sha256이 받은 본문의 증명이 된다.
"받은 본문"은 전송 압축(Content-Encoding: gzip 등)을 requests가 푼 뒤의 바이트다(전선 위 바이트 그대로는 아니다).
"""

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from hashlib import sha256

from trend_pipeline import __version__
from trend_pipeline.feeds import FeedSpec

# 저장된 봉투는 오래 남으므로 형식이 바뀌면 올린다. from_bytes는 모르는 버전을 거부한다.
#   v1: 본문을 디코드한 글자(body)로 저장, sha256은 그 글자를 UTF-8로 다시 인코딩한 값 (계획 1 첫 구현)
#   v2: 받은 바이트를 base64(body_base64)로 저장, sha256은 받은 바이트 값
ENVELOPE_VERSION = 2
CRAWLER_VERSION = __version__

_COMMON_FIELDS = frozenset(
    {
        "envelope_version",
        "source",
        "feed",
        "request_url",
        "requested_at",
        "crawler_version",
        "status",
        "etag",
        "last_modified",
        "content_type",
        "body_sha256",
    }
)
_FIELDS_BY_VERSION = {1: _COMMON_FIELDS | {"body"}, 2: _COMMON_FIELDS | {"body_base64"}}


class EnvelopeIntegrityError(ValueError):
    """저장된 본문이 봉투에 적힌 sha256과 맞지 않는다(손상·변조)."""


@dataclass(frozen=True)
class Envelope:
    envelope_version: int  # 읽은 봉투면 저장된 형식의 버전(v1이면 body는 디코드했던 글자의 UTF-8 바이트)
    source: str
    feed: str
    request_url: str
    requested_at: datetime  # timezone 정보가 있는 UTC 시각
    crawler_version: str
    status: int  # 200 또는 304
    etag: str | None
    last_modified: str | None
    content_type: str | None
    body_sha256: str | None  # body 바이트의 sha256. 304이면 None
    body: bytes | None  # 받은 바이트 그대로. 304이면 None


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
    spec: FeedSpec, requested_at: datetime, status: int, headers: Mapping[str, str], body: bytes | None
) -> Envelope:
    """응답 한 건으로 봉투를 만든다. 200과 304만 받고, 304는 본문 없이 기록한다."""
    if status == 200:
        if body is None:
            raise ValueError("status 200 응답에는 body가 필요하다")
        body_sha256 = sha256(body).hexdigest()
    elif status == 304:
        # 서버가 빈 본문을 보내도 304는 본문이 없는 것으로 통일한다
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
    """봉투를 지금 형식(v2)의 UTF-8 JSON 바이트로 직렬화한다. 같은 봉투는 항상 같은 바이트가 된다."""
    if env.envelope_version != ENVELOPE_VERSION:
        # 옛 형식에서 읽은 봉투는 받은 바이트가 아니므로 지금 형식으로 다시 쓰면 원본인 척하게 된다
        raise ValueError(f"envelope_version {env.envelope_version} 봉투는 다시 쓸 수 없다 (쓰는 형식: {ENVELOPE_VERSION})")
    payload = {
        "envelope_version": env.envelope_version,
        "source": env.source,
        "feed": env.feed,
        "request_url": env.request_url,
        "requested_at": _to_utc(env.requested_at).isoformat(),
        "crawler_version": env.crawler_version,
        "status": env.status,
        "etag": env.etag,
        "last_modified": env.last_modified,
        "content_type": env.content_type,
        "body_sha256": env.body_sha256,
        "body_base64": None if env.body is None else base64.b64encode(env.body).decode("ascii"),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def from_bytes(data: bytes) -> Envelope:
    """저장된 봉투(v1·v2)를 읽고 본문을 sha256과 대조한다.

    모르는 버전·필드는 잘못 읽는 것보다 낫도록 ValueError로 거부한다. 지문이 맞지 않으면 EnvelopeIntegrityError.
    """
    payload = json.loads(data.decode("utf-8"))
    version = payload.get("envelope_version")
    # True == 1, 2.0 == 2라서 dict 조회만으로는 형식이 다른 값도 통과한다. 정수일 때만 찾는다
    expected = _FIELDS_BY_VERSION.get(version) if type(version) is int else None
    if expected is None:
        raise ValueError(f"지원하지 않는 envelope_version: {version!r} (지원: {sorted(_FIELDS_BY_VERSION)})")
    if set(payload) != expected:
        raise ValueError(f"envelope_version {version} 봉투의 필드가 다르다: {sorted(set(payload) ^ expected)}")

    if version == 1:
        text = payload["body"]
        body = None if text is None else text.encode("utf-8")  # v1 sha256은 이 바이트 기준이다
    else:
        encoded = payload["body_base64"]
        try:
            body = None if encoded is None else base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise ValueError(f"body_base64를 읽을 수 없다: {exc}") from exc

    status = payload["status"]
    if type(status) is not int or status not in (200, 304):
        raise ValueError(f"봉투의 status는 200, 304뿐이다 (읽은 값: {status!r})")
    # 본문과 지문을 함께 지운 200은 지문 대조를 통과하므로 따로 막는다(그대로 두면 '0건 성공'으로 기록된다)
    if (status == 200) != (body is not None):
        raise ValueError(f"status {status} 봉투의 본문 유무가 맞지 않는다 (본문 {'있음' if body is not None else '없음'})")

    body_sha256 = payload["body_sha256"]
    actual = None if body is None else sha256(body).hexdigest()
    if actual != body_sha256:
        raise EnvelopeIntegrityError(
            f"{payload['source']}/{payload['feed']} 본문 sha256이 맞지 않는다 (적힌 값 {body_sha256}, 계산 값 {actual})"
        )

    return Envelope(
        envelope_version=version,
        source=payload["source"],
        feed=payload["feed"],
        request_url=payload["request_url"],
        requested_at=_to_utc(datetime.fromisoformat(payload["requested_at"])),
        crawler_version=payload["crawler_version"],
        status=status,
        etag=payload["etag"],
        last_modified=payload["last_modified"],
        content_type=payload["content_type"],
        body_sha256=body_sha256,
        body=body,
    )


def body_text(env: Envelope) -> str | None:
    """본문을 글자로 바꾼다. 304면 None.

    Content-Type에 선언된 charset만 믿고, 없거나 쓸 수 없는 이름이면 UTF-8로 읽는다.
    (requests의 response.text는 charset 없는 text/xml을 ISO-8859-1로 읽어 한글이 깨진다)
    읽을 수 없는 바이트는 대체 문자로 바꿔 처리를 멈추지 않는다. v1 봉투는 이미 디코드했던 글자라 UTF-8로 읽는다.
    """
    if env.body is None:
        return None
    if env.envelope_version == 1 or not env.content_type:
        return env.body.decode("utf-8", errors="replace")
    message = Message()
    message["Content-Type"] = env.content_type
    charset = message.get_content_charset()
    if charset:
        try:
            return env.body.decode(charset, errors="replace")
        except (LookupError, UnicodeError):
            # 모르는 코덱·텍스트 코덱이 아님(LookupError), errors 인자와 상관없이 디코드를 거부하는 코덱
            # (예: undefined → UnicodeError). 어느 쪽이든 처리를 실패시키지 않고 UTF-8로 읽는다
            pass
    return env.body.decode("utf-8", errors="replace")
