from pathlib import Path

import pytest

from trend_pipeline.feeds import FeedSpec, load_feeds


def write_feeds(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "feeds.yml"
    path.write_text(body, encoding="utf-8")
    return path


def test_loads_17_feeds_in_file_order():
    feeds = load_feeds()
    assert len(feeds) == 17
    assert feeds[0] == FeedSpec("yna", "politics", "정치", "https://www.yna.co.kr/rss/politics.xml")
    # 파일 순서 = yna 5개 -> khan 6개 -> donga 6개
    assert [f.source for f in feeds] == ["yna"] * 5 + ["khan"] * 6 + ["donga"] * 6
    assert [f.feed for f in feeds] == [
        "politics", "economy", "society", "international", "culture",
        "politic_news", "economy_news", "society_news", "kh_world", "culture_news", "science_news",
        "politics", "economy", "national", "international", "culture", "science",
    ]


def test_one_feed_per_source_and_category():
    feeds = load_feeds()
    assert len({(f.source, f.category) for f in feeds}) == 17
    assert {f.category for f in feeds} == {"정치", "경제", "사회", "세계", "문화", "IT/과학"}
    assert not [f for f in feeds if f.source == "yna" and f.category == "IT/과학"]


def test_urls_follow_each_source_pattern():
    for f in load_feeds():
        if f.source == "yna":
            assert f.url == f"https://www.yna.co.kr/rss/{f.feed}.xml"
        elif f.source == "khan":
            assert f.url == f"https://www.khan.co.kr/rss/rssdata/{f.feed}.xml"
        else:
            assert f.url == f"https://rss.donga.com/{f.feed}.xml"


def test_feed_spec_is_frozen():
    spec = load_feeds()[0]
    with pytest.raises(AttributeError):
        spec.url = "https://example.com"  # type: ignore[misc]


def test_loads_from_explicit_path(tmp_path):
    path = write_feeds(
        tmp_path,
        "feeds:\n"
        "  - {source: yna, feed: politics, category: 정치, url: 'https://example.com/a.xml'}\n",
    )
    assert load_feeds(path) == [FeedSpec("yna", "politics", "정치", "https://example.com/a.xml")]


def test_rejects_duplicate_source_category(tmp_path):
    path = write_feeds(
        tmp_path,
        "feeds:\n"
        "  - {source: yna, feed: politics, category: 정치, url: 'https://example.com/a.xml'}\n"
        "  - {source: yna, feed: economy, category: 정치, url: 'https://example.com/b.xml'}\n",
    )
    with pytest.raises(ValueError, match=r"\(source, category\) 중복"):
        load_feeds(path)


def test_rejects_duplicate_source_feed(tmp_path):
    # 원본 키가 피드 단위로 유일해야 하므로 (source, feed) 중복도 거부한다
    path = write_feeds(
        tmp_path,
        "feeds:\n"
        "  - {source: yna, feed: politics, category: 정치, url: 'https://example.com/a.xml'}\n"
        "  - {source: yna, feed: politics, category: 경제, url: 'https://example.com/b.xml'}\n",
    )
    with pytest.raises(ValueError, match=r"\(source, feed\) 중복"):
        load_feeds(path)


def test_rejects_unknown_source(tmp_path):
    path = write_feeds(
        tmp_path,
        "feeds:\n"
        "  - {source: hani, feed: politics, category: 정치, url: 'https://example.com/a.xml'}\n",
    )
    with pytest.raises(ValueError, match="hani"):
        load_feeds(path)


def test_rejects_unknown_category(tmp_path):
    path = write_feeds(
        tmp_path,
        "feeds:\n"
        "  - {source: yna, feed: sports, category: 스포츠, url: 'https://example.com/a.xml'}\n",
    )
    with pytest.raises(ValueError, match="스포츠"):
        load_feeds(path)


def test_rejects_entry_with_missing_key(tmp_path):
    path = write_feeds(
        tmp_path,
        "feeds:\n"
        "  - {source: yna, feed: politics, category: 정치}\n",
    )
    with pytest.raises(ValueError, match="url"):
        load_feeds(path)
