"""저장된 RSS 봉투의 XML 본문을 기사 항목(FeedItem)으로 바꾼다. 발행 시각은 항상 UTC aware로 정규화한다."""

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from trend_pipeline.envelope import Envelope

_NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

# HTML 태그는 영문자나 '/'로 시작한다. "<속보>" 같은 말머리는 태그가 아니므로 지우지 않는다
_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_WHITESPACE = re.compile(r"\s+")


class FeedParseError(ValueError):
    """피드 문서 자체를 읽을 수 없다(XML이 깨졌거나 channel이 없다). 항목 단위 실패는 이 예외가 아니다."""


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str
    guid: str | None
    summary: str
    published_at: datetime  # timezone 정보가 있는 UTC 시각


@dataclass(frozen=True)
class ParseResult:
    items: list[FeedItem]
    parse_failed: int  # 읽지 못해 제외한 항목 수


def parse_feed(env: Envelope) -> ParseResult:
    """봉투 본문을 항목 목록으로 바꾼다. 항목 순서는 문서 순서를 따른다.

    본문이 없으면(304) 빈 결과를 돌려준다. 읽을 수 없는 항목은 세어서 제외하고 피드는 계속 처리한다.
    문서 자체가 깨졌으면 FeedParseError를 던진다.
    """
    if env.body is None:
        return ParseResult([], 0)

    where = f"{env.source}/{env.feed}"
    # 서버가 BOM을 보내면 Task 4가 본문에 그대로 남기므로 여기서 한 번만 떼어낸다
    body = env.body.removeprefix("﻿")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FeedParseError(f"{where}: XML을 읽을 수 없다 ({exc})") from exc

    channel = root.find("channel")
    if channel is None:
        raise FeedParseError(f"{where}: <channel>이 없는 문서다 (루트 요소: {root.tag})")

    items: list[FeedItem] = []
    parse_failed = 0
    # 채널 자체의 pubDate 등은 건드리지 않고 <item>만 본다
    for element in channel.findall("item"):
        item = _parse_item(element)
        if item is None:
            parse_failed += 1
        else:
            items.append(item)
    return ParseResult(items, parse_failed)


def _parse_item(element: ET.Element) -> FeedItem | None:
    """항목 하나를 읽는다. 제목·링크·발행 시각 중 하나라도 얻지 못하면 None(=제외)."""
    title = _clean(_text(element.find("title")))
    guid_text = element.findtext("guid", "").strip()
    link = element.findtext("link", "").strip()
    if not link and guid_text.startswith("http"):
        link = guid_text
    published_at = _published_at(element)
    # FeedItem 필드는 비울 수 없다. 링크가 비면 나중에 기사 키도 비어 버린다
    if not title or not link or published_at is None:
        return None

    summary = _clean(_text(element.find("description")))
    if not summary:
        summary = _clean(_text(element.find("content:encoded", _NAMESPACES)))
    return FeedItem(title=title, link=link, guid=guid_text or None, summary=summary, published_at=published_at)


def _text(element: ET.Element | None) -> str:
    # CDATA 없이 태그가 섞여 들어온 경우에도 안쪽 글자까지 모은다
    return "".join(element.itertext()) if element is not None else ""


def _clean(text: str) -> str:
    """HTML 태그 제거 -> 엔티티 해제 -> 연속 공백을 한 칸으로 -> 앞뒤 공백 제거."""
    return _WHITESPACE.sub(" ", html.unescape(_TAG.sub("", text))).strip()


def _published_at(element: ET.Element) -> datetime | None:
    # pubDate(RFC 822)를 먼저, 읽지 못하거나 없으면 dc:date(ISO)를 본다
    candidates = (("pubDate", _parse_rfc822), ("dc:date", _parse_iso))
    for tag, parse in candidates:
        value = element.findtext(tag, "", _NAMESPACES).strip()
        parsed = parse(value) if value else None
        if parsed is None:
            continue
        try:
            return parsed.astimezone(timezone.utc)
        except OverflowError:  # 0001년처럼 UTC로 바꾸면 범위를 벗어나는 값
            continue
    return None


def _parse_rfc822(value: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        # parsedate_to_datetime은 "-0000"과 모르는 시간대 이름("KST" 등)을 모두 naive로 돌려준다.
        # "-0000"은 RSS에서 UTC로 쓰이니 UTC로 보고, 이름만 있는 값은 기준을 알 수 없어 버린다
        if not value.endswith("-0000"):
            return None
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    # 오프셋이 없는 값은 어느 시간대인지 알 수 없어 UTC로 가정하지 않는다
    if parsed.utcoffset() is None:
        return None
    return parsed
