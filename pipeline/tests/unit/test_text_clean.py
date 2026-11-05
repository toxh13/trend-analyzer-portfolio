import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trend_pipeline.envelope import build_envelope
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.parse import parse_feed
from trend_pipeline.text_clean import FORMAT_TAGS, NOTICE_TAGS, CleanTitle, clean_summary, clean_title

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "feeds"
AT = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)


def test_tag_sets():
    assert FORMAT_TAGS == {"속보", "단독", "영상", "포토뉴스", "쇼츠", "특징주"}
    assert NOTICE_TAGS == {"게시판", "부고", "인사"}


# --- clean_title ---


def test_format_tag_removed():
    assert clean_title("[속보]尹 선거법 2심 …").text == "尹 선거법 2심 …"


def test_notice_tag_excludes():
    assert clean_title("[게시판] 행사 안내").excluded is True


def test_topic_tag_unwrapped():
    assert clean_title("[美중간선거] '경합지' …").text.startswith("美중간선거 ")


def test_only_tag_left_gives_empty_text():
    # 머리말만 있는 제목: 빈 문자열이 되고 제외 대상은 아니다(기사는 저장, 키워드만 0개)
    assert clean_title("[속보]") == CleanTitle(text="", excluded=False, tags=("속보",))


def test_title_without_tag_is_unchanged():
    assert clean_title("평범한 제목") == CleanTitle("평범한 제목", False, ())


def test_notice_tag_is_dropped_from_text():
    result = clean_title("[게시판] 행사 안내")
    assert result == CleanTitle("행사 안내", True, ("게시판",))


def test_repeated_leading_tags_read_in_order():
    result = clean_title("[단독][美중간선거] 민주 상원 탈환")
    assert result.text == "美중간선거 민주 상원 탈환"
    assert result.tags == ("단독", "美중간선거")
    assert result.excluded is False


def test_repeated_tags_separated_by_spaces():
    assert clean_title("[속보] [영상] 현장 화면").text == "현장 화면"
    assert clean_title("[속보] [영상] 현장 화면").tags == ("속보", "영상")


def test_fullwidth_brackets_are_read():
    result = clean_title("【속보】 윤석열 2심")
    assert result == CleanTitle("윤석열 2심", False, ("속보",))


def test_mixed_bracket_kinds_and_topic_tag_in_fullwidth():
    result = clean_title("[단독]【美중간선거】 접전")
    assert result.text == "美중간선거 접전"
    assert result.tags == ("단독", "美중간선거")


def test_mismatched_and_fullwidth_brackets_are_read():
    # 실제 yna 제목: 여는 괄호는 반각 '[', 닫는 괄호는 전각 '］'
    result = clean_title("[美중간선거］유권자 출구조사…트럼프 반대 43%")
    assert result == CleanTitle("美중간선거 유권자 출구조사…트럼프 반대 43%", False, ("美중간선거",))
    assert clean_title("［속보］ 제목") == CleanTitle("제목", False, ("속보",))


def test_notice_plus_format_combo():
    result = clean_title("[속보][부고] 고(故) 아무개 별세")
    assert result.excluded is True
    assert result.text == "고(故) 아무개 별세"
    assert result.tags == ("속보", "부고")


def test_notice_after_topic_tag_still_excludes():
    result = clean_title("[美중간선거][인사] 외교부")
    assert result.excluded is True
    assert result.text == "美중간선거 외교부"


def test_bracket_in_the_middle_is_kept():
    title = "에너지음료·운동 부스터, 심정지 보고 비율 11배↑ [건강팩트체크]"
    assert clean_title(title) == CleanTitle(title, False, ())


def test_bracket_after_leading_tag_is_kept():
    result = clean_title("[속보] 고기·생선 안 먹는 90세 [노화설계]")
    assert result.text == "고기·생선 안 먹는 90세 [노화설계]"
    assert result.tags == ("속보",)


def test_mid_title_notice_word_does_not_exclude():
    assert clean_title("올해 행사 [게시판] 개편").excluded is False


def test_tag_inner_text_is_stripped_before_comparison():
    result = clean_title("[ 속보 ] 제목")
    assert result == CleanTitle("제목", False, ("속보",))


def test_tag_without_space_after_it():
    assert clean_title("[미 중간선거]공화당 역풍").text == "미 중간선거 공화당 역풍"


def test_unclosed_bracket_is_not_a_tag():
    assert clean_title("[속보 제목").text == "[속보 제목"


def test_surrounding_and_inner_whitespace_collapsed():
    assert clean_title("  [속보]   앞뒤   공백\t정리  ").text == "앞뒤 공백 정리"


def test_empty_title():
    assert clean_title("") == CleanTitle("", False, ())


# --- clean_summary ---


def test_yna_lead_removed():
    s = "(서울=연합뉴스) 박원희 기자 = 국내 최대 규모의 경쟁 독립영화제"
    assert clean_summary(s) == "국내 최대 규모의 경쟁 독립영화제"


def test_correspondent_lead_removed():
    assert clean_summary("(워싱턴=연합뉴스) 홍길동 특파원 = 미국 중간선거") == "미국 중간선거"


def test_multi_name_byline_removed():
    assert clean_summary("(서울=연합뉴스) 김철수 이영희 기자 = 본문") == "본문"


def test_senior_reporter_and_stringer_bylines_removed():
    assert clean_summary("(서울=연합뉴스) 한승호 선임기자 = 세계 최고 부자") == "세계 최고 부자"
    assert clean_summary("(애틀랜타=연합뉴스) 이종원 통신원 = 3일(현지시간)") == "3일(현지시간)"


def test_dateline_with_nested_brackets_removed():
    s = "(피바디[미 매사추세츠주]=연합뉴스) 김철수 기자 = 본문"
    assert clean_summary(s) == "본문"


def test_dateline_without_byline_removed():
    assert clean_summary("(서울=연합뉴스) 4일 국고채 금리가 일제히 하락하고 있다.") == "4일 국고채 금리가 일제히 하락하고 있다."


def test_byline_without_dateline_removed():
    assert clean_summary("박원희 기자 = 본문") == "본문"


def test_trailing_photo_credit_removed():
    assert clean_summary("현장에서 시민들이 손을 흔들고 있다. 연합뉴스") == "현장에서 시민들이 손을 흔들고 있다."


@pytest.mark.parametrize(
    "tail",
    [" 연합뉴스", "/연합뉴스", " /연합뉴스", "ⓒ연합뉴스", " ⓒ 뉴스1", "/뉴스1", " 뉴시스", "/경향신문", " ⓒ동아일보", "/ 동아일보 "],
)
def test_trailing_credit_forms_removed(tail):
    assert clean_summary("사진 설명이다." + tail) == "사진 설명이다."


def test_credit_in_the_middle_is_kept():
    s = "포즈를 취하고 있다. 연합뉴스그룹 리센느가 새 앨범을 냈다."
    assert clean_summary(s) == s


def test_lead_and_trailing_credit_both_removed():
    s = "(서울=연합뉴스) 박원희 기자 = 본문이다. /연합뉴스"
    assert clean_summary(s) == "본문이다."


def test_unmatched_text_unchanged():
    s = "배우 차예련 측이 학교폭력 의혹을 재차 일축했다."
    assert clean_summary(s) == s


def test_lone_open_paren_summary_unchanged():
    # 연합뉴스 포토 기사의 실제 description
    assert clean_summary("(") == "("


def test_parenthesis_without_equals_is_not_a_dateline():
    assert clean_summary("(09:00)") == "(09:00)"
    assert clean_summary("(사진) 설명이다") == "(사진) 설명이다"


def test_dateline_only_in_middle_is_kept():
    s = "본문이다 (서울=연합뉴스) 박원희 기자 = 이어진다"
    assert clean_summary(s) == s


def test_empty_summary():
    assert clean_summary("") == ""


def test_summary_whitespace_collapsed():
    assert clean_summary("  (서울=연합뉴스) 박원희 기자 =  본문   두 줄 \n 입니다  ") == "본문 두 줄 입니다"


# --- 실제 피드 ---


def _fixture_items(prefix: str):
    for path in sorted(FIXTURES.glob(f"{prefix}_*.xml")):
        source, _, rest = path.name.partition("_")
        spec = FeedSpec(source=source, feed=rest.removesuffix(".xml"), category="정치", url="https://example.com/x.xml")
        yield from parse_feed(build_envelope(spec, AT, 200, {}, path.read_bytes())).items


def test_real_yna_summaries_lose_dateline_and_byline():
    leftover = re.compile(r"^\([^()]*=[^()]*\)|^[가-힣 ]{2,20}(?:기자|특파원|통신원) =")
    items = list(_fixture_items("yna"))
    assert items
    for item in items:
        assert not leftover.match(clean_summary(item.summary)), item.summary


def test_real_titles_keep_text_and_notice_tags_exclude():
    items = [item for prefix in ("yna", "khan", "donga") for item in _fixture_items(prefix)]
    notices = 0
    for item in items:
        result = clean_title(item.title)
        assert not result.text.startswith(("[", "【"))
        notices += result.excluded
    assert notices > 0
    assert clean_title("[속보]尹 선거법 2심 당선무효형 유지…국힘 392억원 반환 비상").text.startswith("尹 선거법")
