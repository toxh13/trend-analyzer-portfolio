from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from trend_pipeline.envelope import Envelope, build_envelope
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.parse import FeedItem, FeedParseError, ParseResult, parse_feed

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "feeds"
SPEC = FeedSpec(source="yna", feed="politics", category="정치", url="https://example.com/rss/politics.xml")
AT = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
UTC_INSTANT = datetime(2026, 11, 4, 4, 11, 5, tzinfo=timezone.utc)

RSS_OPEN = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"'
    ' xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>t</title>'
    "<pubDate>Wed, 04 Nov 2026 14:00:00 +0900</pubDate>"
)
RSS_CLOSE = "</channel></rss>"


def env_for(body: str, spec: FeedSpec = SPEC) -> Envelope:
    return build_envelope(spec, AT, 200, {}, body)


def fixture_env(name: str) -> Envelope:
    source, _, rest = name.partition("_")
    spec = FeedSpec(source=source, feed=rest.removesuffix(".xml"), category="정치", url="https://example.com/x.xml")
    return env_for((FIXTURES / name).read_text(encoding="utf-8"), spec)


def rss(*items: str) -> str:
    return RSS_OPEN + "".join(f"<item>{body}</item>" for body in items) + RSS_CLOSE


def item_xml(
    title: str | None = "제목",
    link: str | None = "https://example.com/a/1",
    pub: str | None = "Wed, 04 Nov 2026 13:11:05 +0900",
    extra: str = "",
) -> str:
    parts = []
    if title is not None:
        parts.append(f"<title>{title}</title>")
    if link is not None:
        parts.append(f"<link>{link}</link>")
    if pub is not None:
        parts.append(f"<pubDate>{pub}</pubDate>")
    return "".join(parts) + extra


def parse_one(body: str) -> FeedItem:
    result = parse_feed(env_for(body))
    assert result.parse_failed == 0
    assert len(result.items) == 1
    return result.items[0]


# --- 고정 샘플 -------------------------------------------------------------


@pytest.mark.parametrize(
    "name,count",
    [("yna_politics.xml", 120), ("khan_politics.xml", 50), ("donga_politics.xml", 50)],
)
def test_parses_fixture_item_counts(name, count):
    result = parse_feed(fixture_env(name))
    assert len(result.items) == count
    assert result.parse_failed == 0


def test_every_fixture_parses_with_utc_aware_times():
    names = sorted(path.name for path in FIXTURES.glob("*.xml"))
    assert len(names) == 17
    for name in names:
        result = parse_feed(fixture_env(name))  # FeedParseError가 나면 실패
        assert result.items, name
        for item in result.items:
            assert item.title and item.link, name
            assert item.published_at.utcoffset() == timedelta(0), name


def test_fixture_first_items_match_known_values():
    yna = parse_feed(fixture_env("yna_politics.xml")).items[0]
    assert yna.title == '라이더들 "배달앱 수수료 상한제 법안 반대…생존권 위협"'
    assert yna.link == "https://www.yna.co.kr/view/AKR20261104121000030"
    assert yna.guid == "https://www.yna.co.kr/view/AKR20261104121000030"
    assert yna.published_at == datetime(2026, 11, 4, 5, 52, 11, tzinfo=timezone.utc)  # 14:52:11 KST
    assert yna.summary.startswith("(서울=연합뉴스) 홍국기 기자")

    khan = parse_feed(fixture_env("khan_politics.xml")).items[0]
    assert khan.published_at == datetime(2026, 11, 4, 3, 23, tzinfo=timezone.utc)  # 12:23 KST, dc:date
    assert "&amp;" not in khan.link and "utm_source=khan_rss&utm_medium=rss" in khan.link

    donga = parse_feed(fixture_env("donga_politics.xml")).items[0]
    assert donga.guid is None  # 동아일보 항목에는 guid가 없다
    assert donga.link.startswith("https://www.donga.com/news/Politics/article/")
    assert "<img" not in donga.summary  # 요약 앞의 <img> 태그가 제거된다
    assert donga.summary.startswith("북한이 5000t급 구축함을")


def test_channel_pubdate_is_not_an_item():
    # 채널 자체의 pubDate가 있어도 <item>만 센다
    result = parse_feed(env_for(rss()))
    assert result == ParseResult([], 0)


# --- 시각 ------------------------------------------------------------------


def test_timezones_normalized_to_utc():
    # Review Focus 5: 표기가 달라도 같은 UTC 순간이 되어야 한다
    values = {
        "Wed, 04 Nov 2026 13:11:05 +0900": item_xml(pub="Wed, 04 Nov 2026 13:11:05 +0900"),
        "2026-11-04T13:11:05+09:00": item_xml(pub=None, extra="<dc:date>2026-11-04T13:11:05+09:00</dc:date>"),
        "Wed, 04 Nov 2026 04:11:05 GMT": item_xml(pub="Wed, 04 Nov 2026 04:11:05 GMT"),
    }
    for label, xml in values.items():
        item = parse_one(rss(xml))
        assert item.published_at == UTC_INSTANT, label
        assert item.published_at.tzinfo is not None
        assert item.published_at.utcoffset() == timedelta(0), label


def test_iso_z_suffix_is_utc():
    item = parse_one(rss(item_xml(pub=None, extra="<dc:date>2026-11-04T04:11:05Z</dc:date>")))
    assert item.published_at == UTC_INSTANT


def test_pubdate_is_preferred_over_dc_date():
    xml = item_xml(pub="Wed, 04 Nov 2026 04:11:05 GMT", extra="<dc:date>2000-01-01T00:00:00+00:00</dc:date>")
    assert parse_one(rss(xml)).published_at == UTC_INSTANT


def test_unreadable_pubdate_falls_back_to_dc_date():
    xml = item_xml(pub="어제 오후", extra="<dc:date>2026-11-04T13:11:05+09:00</dc:date>")
    assert parse_one(rss(xml)).published_at == UTC_INSTANT


def test_rfc822_minus_zero_offset_is_utc():
    # -0000은 "시간대 모름"을 뜻하지만 RSS에서는 UTC로 쓰이므로 UTC로 본다
    item = parse_one(rss(item_xml(pub="Wed, 04 Nov 2026 04:11:05 -0000")))
    assert item.published_at == UTC_INSTANT
    assert item.published_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "pub",
    [
        "Wed, 04 Nov 2026 04:11:05 KST",  # 알 수 없는 시간대 이름 -> 기준을 모른다
        "Wed, 04 Nov 2026 04:11:05",  # 시간대 없음
        "not a date",
        "",
    ],
)
def test_unusable_rfc822_pubdate_is_parse_failed(pub):
    result = parse_feed(env_for(rss(item_xml(pub=pub))))
    assert result.items == []
    assert result.parse_failed == 1


@pytest.mark.parametrize(
    "pub",
    [
        # parsedate_to_datetime이 ValueError가 아니라 OverflowError를 던지는 값들
        "Wed, 04 Nov 2026 04:11:05 +99999999999999999999",
        "Wed, 99999999999999999999 Nov 2026 04:11:05 GMT",
        "Wed, 04 Nov 2026 99999999999999999999:11:05 GMT",
    ],
)
def test_overflowing_rfc822_pubdate_is_parse_failed_not_fatal(pub):
    # 터무니없이 큰 숫자 하나가 피드 전체를 죽이면 안 된다: 그 항목만 세고 나머지는 계속
    body = rss(
        item_xml(title="앞", link="https://example.com/a/1"),
        item_xml(title="큰 숫자", link="https://example.com/a/2", pub=pub),
        item_xml(title="뒤", link="https://example.com/a/3"),
    )
    result = parse_feed(env_for(body))
    assert [i.title for i in result.items] == ["앞", "뒤"]
    assert result.parse_failed == 1


@pytest.mark.parametrize("dc_date", ["0001-01-01T00:00:00+09:00", "9999-12-31T23:59:59-09:00"])
def test_iso_value_out_of_range_after_utc_conversion_is_parse_failed(dc_date):
    # 읽기는 되지만 UTC로 바꾸면 datetime 범위를 벗어나는 값(astimezone의 OverflowError)
    body = rss(
        item_xml(title="앞", link="https://example.com/a/1"),
        item_xml(title="범위 밖", link="https://example.com/a/2", pub=None, extra=f"<dc:date>{dc_date}</dc:date>"),
    )
    result = parse_feed(env_for(body))
    assert [i.title for i in result.items] == ["앞"]
    assert result.parse_failed == 1


def test_out_of_range_pubdate_falls_back_to_valid_dc_date():
    # pubDate가 범위를 벗어나도 dc:date가 멀쩡하면 그 값을 쓴다
    xml = item_xml(
        pub="Fri, 31 Dec 9999 23:59:59 -0900", extra="<dc:date>2026-11-04T13:11:05+09:00</dc:date>"
    )
    assert parse_one(rss(xml)).published_at == UTC_INSTANT


@pytest.mark.parametrize("dc_date", ["2026-11-04T13:11:05", "2026-11-04", "yesterday", ""])
def test_naive_or_unreadable_iso_is_parse_failed(dc_date):
    # 오프셋이 없는 ISO 값은 어느 시간대인지 알 수 없어 UTC로 가정하지 않는다
    result = parse_feed(env_for(rss(item_xml(pub=None, extra=f"<dc:date>{dc_date}</dc:date>"))))
    assert result.items == []
    assert result.parse_failed == 1


def test_item_without_pubdate_is_counted_not_fatal():
    # Review Focus 1: 발행 시각이 없는 항목만 세고 제외, 나머지는 계속 처리
    body = rss(
        item_xml(title="앞", link="https://example.com/a/1"),
        item_xml(title="시각 없음", link="https://example.com/a/2", pub=None),
        item_xml(title="뒤", link="https://example.com/a/3"),
    )
    result = parse_feed(env_for(body))
    assert [i.title for i in result.items] == ["앞", "뒤"]  # 문서 순서 유지
    assert result.parse_failed == 1


# --- 제목 · 링크 · guid ----------------------------------------------------


@pytest.mark.parametrize("title", [None, "", "   ", "<b></b>", "<![CDATA[ ]]>"])
def test_item_with_empty_title_is_parse_failed(title):
    result = parse_feed(env_for(rss(item_xml(title=title))))
    assert result.items == []
    assert result.parse_failed == 1


def test_item_with_empty_link_and_no_usable_guid_is_parse_failed():
    for extra in ["", "<guid></guid>", "<guid>urn:uuid:1234</guid>", "<guid>  </guid>"]:
        result = parse_feed(env_for(rss(item_xml(link=None, extra=extra))))
        assert result.items == [], extra
        assert result.parse_failed == 1, extra
    # 공백뿐인 <link>도 비어 있는 것으로 본다
    result = parse_feed(env_for(rss(item_xml(link="   "))))
    assert (result.items, result.parse_failed) == ([], 1)


def test_empty_link_falls_back_to_http_guid():
    item = parse_one(rss(item_xml(link=None, extra="<guid>  https://example.com/g/9  </guid>")))
    assert item.link == "https://example.com/g/9"
    assert item.guid == "https://example.com/g/9"


def test_link_is_stripped_and_guid_kept_as_is_when_link_present():
    item = parse_one(rss(item_xml(link="\n  https://example.com/a/1 \n", extra="<guid>tag:example.com,1</guid>")))
    assert item.link == "https://example.com/a/1"
    assert item.guid == "tag:example.com,1"


def test_missing_or_empty_guid_is_none():
    assert parse_one(rss(item_xml())).guid is None
    assert parse_one(rss(item_xml(extra="<guid>  </guid>"))).guid is None


def test_title_is_cleaned_like_summary():
    item = parse_one(rss(item_xml(title="  <b>[속보]</b>   삼성 &amp; 현대 \n 협력  ")))
    assert item.title == "[속보] 삼성 & 현대 협력"


def test_angle_bracket_label_that_is_not_html_is_kept():
    # <속보> 같은 말머리는 HTML 태그가 아니므로 지우지 않는다
    item = parse_one(rss(item_xml(title="&lt;속보&gt; 북한 발사")))
    assert item.title == "<속보> 북한 발사"


# --- 요약 ------------------------------------------------------------------


def test_html_in_description_is_stripped_and_unescaped():
    desc = "<![CDATA[<p>본문 <b>강조</b> &amp; 인용 &quot;따옴표&quot;</p><br/>\n<img src='a.jpg' align='left'>둘째&nbsp;줄]]>"
    item = parse_one(rss(item_xml(extra=f"<description>{desc}</description>")))
    assert item.summary == '본문 강조 & 인용 "따옴표" 둘째 줄'


def test_description_without_cdata_is_cleaned_too():
    # CDATA 없이 이스케이프된 HTML: XML 파서가 한 겹 풀고, 우리가 태그를 제거한다
    desc = "&lt;p&gt;가 &amp;amp; 나&lt;/p&gt;"
    item = parse_one(rss(item_xml(extra=f"<description>{desc}</description>")))
    assert item.summary == "가 & 나"


def test_summary_falls_back_to_content_encoded():
    xml = item_xml(extra="<description> <br/> </description><content:encoded><![CDATA[<p>전문 &amp; 내용</p>]]></content:encoded>")
    assert parse_one(rss(xml)).summary == "전문 & 내용"
    xml = item_xml(extra="<content:encoded><![CDATA[<p>전문</p>]]></content:encoded>")
    assert parse_one(rss(xml)).summary == "전문"


def test_description_wins_over_content_encoded():
    xml = item_xml(extra="<description>짧은 요약</description><content:encoded>긴 전문</content:encoded>")
    assert parse_one(rss(xml)).summary == "짧은 요약"


def test_summary_is_empty_string_when_both_missing():
    assert parse_one(rss(item_xml())).summary == ""


# --- 문서 수준 -------------------------------------------------------------


def test_broken_xml_raises_feed_parse_error():
    env = env_for("<rss><channel><item><title>끊김")
    with pytest.raises(FeedParseError) as excinfo:
        parse_feed(env)
    assert "yna/politics" in str(excinfo.value)


@pytest.mark.parametrize(
    "body",
    [
        "",
        "<html><body>점검 중</body></html>",
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>a</title></entry></feed>',
        "<rss version='2.0'></rss>",
    ],
)
def test_document_without_channel_raises_feed_parse_error(body):
    with pytest.raises(FeedParseError) as excinfo:
        parse_feed(env_for(body))
    assert "yna/politics" in str(excinfo.value)


def test_feed_parse_error_is_a_value_error():
    assert issubclass(FeedParseError, ValueError)


def test_304_envelope_returns_empty_result():
    env = build_envelope(SPEC, AT, 304, {"ETag": '"x"'}, None)
    assert env.body is None
    assert parse_feed(env) == ParseResult([], 0)


def test_leading_bom_is_ignored():
    body = "﻿" + rss(item_xml())
    result = parse_feed(env_for(body))
    assert len(result.items) == 1
    assert result.parse_failed == 0


def test_feed_with_no_items_is_an_empty_result():
    assert parse_feed(env_for(rss())) == ParseResult([], 0)


def test_results_are_frozen_dataclasses():
    item = parse_one(rss(item_xml()))
    with pytest.raises(AttributeError):
        item.title = "x"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        ParseResult([], 0).parse_failed = 1  # type: ignore[misc]
