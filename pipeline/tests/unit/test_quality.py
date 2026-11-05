from datetime import datetime, timezone

from trend_pipeline.article_key import ArticleKey
from trend_pipeline.parse import FeedItem
from trend_pipeline.quality import QualityReport, check_items

PUBLISHED = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)


def _item(
    source="yna",
    source_article_id="AKR20261104000001",
    title="제목",
    link="https://www.yna.co.kr/view/AKR20261104000001",
    published_at=PUBLISHED,
):
    key = ArticleKey(source, source_article_id)
    return key, FeedItem(title=title, link=link, guid=None, summary="요약", published_at=published_at)


def test_empty_list_is_all_zero():
    assert check_items([]) == QualityReport(0, 0, 0)


def test_clean_items():
    items = [_item(source_article_id=f"AKR{i}", link=f"https://www.yna.co.kr/view/AKR{i}") for i in range(5)]
    assert check_items(items) == QualityReport(item_count=5, missing_required=0, duplicate_keys=0)


def test_quality_counts_duplicates_and_missing():
    items = [
        _item(source_article_id="AKR1"),
        _item(source_article_id="AKR1"),  # AKR1 중복
        _item(source_article_id="AKR2", title=""),  # 제목 비어 있음
        _item(source_article_id="AKR3"),
    ]
    assert check_items(items) == QualityReport(item_count=4, missing_required=1, duplicate_keys=1)


def test_three_copies_of_one_key_count_two_duplicates():
    items = [_item(source_article_id="AKR1") for _ in range(3)] + [_item(source_article_id="AKR2")]
    report = check_items(items)
    assert report.item_count == 4
    assert report.duplicate_keys == 2


def test_same_article_id_in_different_sources_is_not_duplicate():
    items = [_item(source="yna", source_article_id="1"), _item(source="khan", source_article_id="1")]
    assert check_items(items).duplicate_keys == 0


def test_empty_string_and_blank_fields_count_as_missing():
    items = [
        _item(source_article_id="a", title=""),
        _item(source_article_id="b", link=""),
        _item(source_article_id="c", title="   \t"),
        _item(source_article_id="d", title="\n"),
        _item(source_article_id="e", title="　"),  # 전각 공백
        _item(source_article_id="", link="https://x/1"),
        _item(source_article_id="ok"),
    ]
    report = check_items(items)
    assert report.item_count == 7
    assert report.missing_required == 6


def test_none_fields_count_as_missing():
    items = [
        _item(source_article_id="a", published_at=None),
        _item(source_article_id="b", title=None),
        _item(source_article_id="c", link=None),
        _item(source_article_id="ok"),
    ]
    assert check_items(items).missing_required == 3


def test_row_missing_several_fields_is_counted_once():
    items = [_item(source_article_id="a", title="", link="", published_at=None)]
    assert check_items(items) == QualityReport(1, 1, 0)


def test_korean_and_newlines_survive_the_jsonl_round_trip():
    items = [
        _item(source_article_id="a", title="속보\n두 줄 제목 \"따옴표\" 한글"),
        _item(source_article_id="b", title="다른 제목"),
    ]
    assert check_items(items) == QualityReport(item_count=2, missing_required=0, duplicate_keys=0)
