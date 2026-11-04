"""기사 식별 키와 화면에 저장할 표시 링크. 같은 기사는 링크 꼬리표(utm, 섹션 번호)가 달라도 같은 키가 나온다."""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

# 매체별 기사 번호 패턴. 링크 → (http로 시작하면) guid 순으로 찾는다
_ID_PATTERNS = {
    "yna": re.compile(r"/view/(AKR\d+)"),  # 연합뉴스: /view/AKR20261104055151504
    "khan": re.compile(r"/article/(\d+)"),  # 경향: /article/202611041132001/?utm_source=... (utm은 무시)
    "donga": re.compile(r"/article/all/\d{8}/(\d+)/"),  # 동아: .../20261104/134963513/1 · /2 는 같은 기사
}


@dataclass(frozen=True)
class ArticleKey:
    """기사의 정체성. 적재 시 UNIQUE(source, source_article_id)의 값이 된다."""

    source: str
    source_article_id: str


def _normalized_url(link: str) -> str:
    # 번호를 못 뽑을 때의 대체 키: https, 소문자 호스트, 쿼리·#조각 제거, 끝 '/' 제거(경로 대소문자는 유지)
    parts = urlsplit(link.strip())
    return f"https://{parts.netloc.lower()}{parts.path.rstrip('/')}"


def article_key(source: str, link: str, guid: str | None) -> ArticleKey:
    """매체별 패턴으로 기사 번호를 뽑는다. 못 뽑으면 정규화한 링크 URL을 번호로 쓴다."""
    pattern = _ID_PATTERNS.get(source)
    if pattern is not None:
        candidates = [link]
        if guid is not None and guid.strip().startswith("http"):
            candidates.append(guid.strip())
        for url in candidates:
            match = pattern.search(url)
            if match:
                return ArticleKey(source, match.group(1))
    return ArticleKey(source, _normalized_url(link))


def display_link(source: str, link: str, guid: str | None) -> str:
    """저장·표시용 링크. http로 시작하는 guid가 있으면 그대로, 없으면 쿼리·#조각·끝 '/'를 뗀 링크.

    source는 article_key와 같은 호출 모양을 맞추려고 받는다(현재 매체별 차이는 없다).
    """
    if guid is not None and guid.strip().startswith("http"):
        return guid.strip()
    parts = urlsplit(link.strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
