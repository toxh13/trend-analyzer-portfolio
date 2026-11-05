"""제목 머리말과 요약 앞뒤의 기사 틀(기자 줄, 사진 출처)을 걷어내는 텍스트 정리."""

import re
from dataclasses import dataclass

# 형식 태그: 내용이 아니라 기사 형식을 알리는 말머리. 지우고 제목에는 남기지 않는다
FORMAT_TAGS = frozenset({"속보", "단독", "영상", "포토뉴스", "쇼츠", "특징주"})
# 공지 태그: 뉴스가 아닌 안내성 기사. 머리말을 지우고 excluded=True 로 알려 적재에서 뺀다
NOTICE_TAGS = frozenset({"게시판", "부고", "인사"})

_WHITESPACE = re.compile(r"\s+")

# 제목 맨 앞의 [...] 또는 【...】 한 덩어리와 뒤따르는 공백. 닫는 괄호가 없으면 태그가 아니다.
# 실제 피드에 "[美중간선거］"처럼 반각·전각 괄호가 섞인 제목이 있어 여닫는 괄호는 종류를 가리지 않는다
_LEADING_TAG = re.compile(r"[\[［【]([^\]］】]*)[\]］】]\s*")

# 요약 맨 앞의 "(서울=연합뉴스)" 같은 발신지 줄. 지명 안의 [ ] 는 허용하고 ( ) 는 허용하지 않는다
_DATELINE = re.compile(r"^\([^()=]*=[^()]*\)\s*")
# 그 뒤의 "박원희 기자 =" 기자 줄. 한글 이름이 여럿일 수 있고 직함은 기자·선임기자·특파원·통신원
_BYLINE = re.compile(r"^(?:[가-힣]{2,4}\s+)+(?:(?:선임)?기자|특파원|통신원)\s*=\s*")
# 요약 끝의 사진 출처. 앞에 '/' 나 'ⓒ' 가 붙어도 되고, 글 중간에 나오는 매체명은 건드리지 않는다
_TRAILING_CREDIT = re.compile(r"[\s/ⓒ]*(?:연합뉴스|뉴스1|뉴시스|경향신문|동아일보)\s*$")


@dataclass(frozen=True)
class CleanTitle:
    text: str  # 머리말을 정리한 제목. 머리말뿐이었다면 빈 문자열
    excluded: bool  # 공지 태그가 있어 기사를 적재하지 않을 제목
    tags: tuple[str, ...]  # 읽은 앞쪽 머리말의 안쪽 글자, 읽은 순서대로


def clean_title(title: str) -> CleanTitle:
    """제목 앞의 머리말을 반복해서 읽고 종류별로 처리한다. 앞쪽이 아닌 괄호는 그대로 둔다.

    형식 태그는 지우고, 공지 태그는 지우면서 excluded=True 를 켜고,
    그 밖의 태그는 괄호만 벗겨 내용을 제목에 남긴다("[美중간선거] 접전" → "美중간선거 접전").
    """
    rest = title.strip()
    tags: list[str] = []
    kept: list[str] = []  # 괄호만 벗겨 제목에 남길 태그 내용
    excluded = False
    while (match := _LEADING_TAG.match(rest)) is not None:
        inner = match.group(1).strip()
        tags.append(inner)
        if inner in NOTICE_TAGS:
            excluded = True
        elif inner not in FORMAT_TAGS:
            kept.append(inner)
        rest = rest[match.end() :]
    # 남긴 태그는 모두 제목 맨 앞에 있었으므로 본문 앞에 순서대로 붙인다
    text = _WHITESPACE.sub(" ", " ".join([*kept, rest])).strip()
    return CleanTitle(text=text, excluded=excluded, tags=tuple(tags))


def clean_summary(summary: str) -> str:
    """요약 앞의 발신지·기자 줄과 끝의 사진 출처를 지운다. 해당하지 않는 글은 공백만 정리해 그대로 둔다."""
    text = summary.strip()
    text = _DATELINE.sub("", text, count=1)
    text = _BYLINE.sub("", text, count=1)
    text = _TRAILING_CREDIT.sub("", text, count=1)
    return _WHITESPACE.sub(" ", text).strip()
