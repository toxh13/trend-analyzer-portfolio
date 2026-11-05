from datetime import datetime, timezone
from pathlib import Path

import pytest

from trend_pipeline.article_key import ArticleKey, article_key, display_link
from trend_pipeline.envelope import build_envelope
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.parse import parse_feed

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "feeds"
AT = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)

KHAN_LINK = "https://www.khan.co.kr/article/202611041132001/?utm_source=khan_rss&utm_medium=rss"
KHAN_GUID = "https://www.khan.co.kr/article/202611041132001"


def test_yna():
    assert article_key("yna", "https://www.yna.co.kr/view/AKR20261104055151504", None) == ArticleKey(
        "yna", "AKR20261104055151504"
    )


def test_khan_ignores_utm():
    assert article_key("khan", KHAN_LINK, KHAN_GUID).source_article_id == "202611041132001"


def test_donga_same_article_with_suffix_1_and_2():
    a = article_key("donga", "https://www.donga.com/news/Politics/article/all/20261104/134963513/1", None)
    b = article_key("donga", "https://www.donga.com/news/Politics/article/all/20261104/134963513/2", None)
    assert a == b == ArticleKey("donga", "134963513")


def test_donga_real_fixture_link():
    # donga_national.xml 에 실제로 있는 링크(섹션 경로가 Society)
    link = "https://www.donga.com/news/Society/article/all/20261104/134964674/1"
    assert article_key("donga", link, None) == ArticleKey("donga", "134964674")


def test_donga_link_ending_with_slash_after_id_matches():
    link = "https://www.donga.com/news/Politics/article/all/20261104/134963513/"
    assert article_key("donga", link, None).source_article_id == "134963513"


def test_donga_link_without_trailing_slash_after_id_falls_back_to_url():
    # 패턴은 id 뒤 '/'를 요구한다. 못 뽑으면 정규화 URL로 간다
    link = "https://www.donga.com/news/Politics/article/all/20261104/134963513"
    assert article_key("donga", link, None).source_article_id == link


def test_key_is_stable_across_utm_variants():
    other = "https://www.khan.co.kr/article/202611041132001/?utm_source=x&utm_campaign=y"
    assert article_key("khan", KHAN_LINK, None) == article_key("khan", other, None)


def test_guid_used_when_link_has_no_match():
    # 링크는 패턴에 안 맞고, http로 시작하는 guid는 맞는다
    key = article_key("yna", "https://www.yna.co.kr/short/abc", "https://www.yna.co.kr/view/AKR20261104055151504")
    assert key == ArticleKey("yna", "AKR20261104055151504")


def test_link_match_wins_over_guid():
    key = article_key("khan", KHAN_LINK, "https://www.khan.co.kr/article/999999999999999")
    assert key.source_article_id == "202611041132001"


def test_non_http_guid_is_ignored():
    key = article_key("yna", "https://www.yna.co.kr/short/abc", "AKR20261104055151504")
    assert key.source_article_id == "https://www.yna.co.kr/short/abc"


def test_fallback_normalized_url():
    link = "http://WWW.Example.COM/News/Item/?id=1&utm_source=x#top"
    assert article_key("yna", link, None) == ArticleKey("yna", "https://www.example.com/News/Item")


def test_fallback_strips_trailing_slash_and_keeps_path_case():
    assert article_key("khan", "https://Example.com/A/b/", None).source_article_id == "https://example.com/A/b"


def test_fallback_for_root_path():
    assert article_key("khan", "https://example.com/?x=1", None).source_article_id == "https://example.com"


def test_unknown_source_uses_normalized_url():
    link = "https://example.com/view/AKR1/"
    assert article_key("other", link, None) == ArticleKey("other", "https://example.com/view/AKR1")


def test_article_key_is_hashable_identity():
    assert len({ArticleKey("yna", "A"), ArticleKey("yna", "A"), ArticleKey("khan", "A")}) == 2


def test_display_link_prefers_guid_and_strips_utm():
    assert display_link("khan", KHAN_LINK, KHAN_GUID) == KHAN_GUID
    # guid가 없으면 쿼리와 끝 '/'를 뗀 링크
    assert display_link("khan", KHAN_LINK, None) == KHAN_GUID


def test_display_link_without_guid_removes_query_fragment_and_trailing_slash():
    assert display_link("donga", "https://www.donga.com/a/b/?x=1#frag", None) == "https://www.donga.com/a/b"


def test_display_link_without_guid_keeps_donga_suffix():
    link = "https://www.donga.com/news/Politics/article/all/20261104/134963513/1"
    assert display_link("donga", link, None) == link


def test_display_link_guid_is_stripped_and_returned_as_is():
    assert display_link("yna", "https://www.yna.co.kr/view/AKR1?x=1", "  https://www.yna.co.kr/view/AKR1?x=1 ") == (
        "https://www.yna.co.kr/view/AKR1?x=1"
    )


def test_display_link_non_http_guid_falls_back_to_link():
    assert display_link("yna", "https://www.yna.co.kr/view/AKR1/?a=b", "AKR1") == "https://www.yna.co.kr/view/AKR1"


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.xml")), ids=lambda p: p.name)
def test_real_fixture_items_get_publisher_ids(path):
    source, _, rest = path.name.partition("_")
    spec = FeedSpec(source=source, feed=rest.removesuffix(".xml"), category="정치", url="https://example.com/x.xml")
    result = parse_feed(build_envelope(spec, AT, 200, {}, path.read_bytes()))
    assert result.items
    for item in result.items:
        key = article_key(source, item.link, item.guid)
        # 발행처 패턴으로 id를 뽑았다면 URL이 아니다(정규화 URL로 떨어지지 않았다)
        assert key.source_article_id.isalnum(), item.link
        assert "?" not in display_link(source, item.link, item.guid)
