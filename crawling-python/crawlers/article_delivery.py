from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DeliveryResult:
    """백엔드 전송 결과입니다. acknowledged는 실제 신규 저장 건수와 다를 수 있습니다."""

    selected: int
    preprocessing_failed: int
    backend_acknowledged: int
    http_failed: int
    transport_failed: int

    @property
    def post_attempted(self) -> int:
        return self.backend_acknowledged + self.http_failed + self.transport_failed

    @property
    def failed(self) -> int:
        return self.preprocessing_failed + self.http_failed + self.transport_failed


SUMMARY_MAX_LENGTH = 150


def summarize_content(content: str) -> str:
    """본문 앞 150자를 요약으로 쓰고, 잘린 경우에만 '...'을 붙입니다."""
    return content[:SUMMARY_MAX_LENGTH] + "..." if len(content) > SUMMARY_MAX_LENGTH else content


def preprocess_article(article: dict, keyword_extractor: Callable) -> dict:
    """기사 원본은 그대로 두고, 키워드·요약을 붙이고 본문을 뺀 사본을 만듭니다.

    v1 HTTP 전송 경로와 v2 파일 출력 경로가 같은 규칙을 쓰도록 공용 함수로 둡니다.
    """
    payload = article.copy()
    payload["keywords"] = keyword_extractor(payload["content"])
    payload["summary"] = summarize_content(payload["content"])
    del payload["content"]
    return payload


def deliver_articles(session, endpoint: str, articles: list[dict], keyword_extractor: Callable) -> DeliveryResult:
    """선택된 기사를 가공해 백엔드로 보내고 각 실패 지점을 집계합니다."""
    preprocessing_failed = 0
    backend_acknowledged = 0
    http_failed = 0
    transport_failed = 0

    for article in articles:
        try:
            payload = preprocess_article(article, keyword_extractor)
        except Exception as exc:
            preprocessing_failed += 1
            print(f"article preprocessing failed: {exc}")
            continue

        try:
            response = session.post(endpoint, json=payload, timeout=10)
        except Exception as exc:
            transport_failed += 1
            print(f"article transport failed: {exc}")
            continue

        if response.status_code in (200, 201):
            backend_acknowledged += 1
            print(f"send success url={payload['sourceUrl'][:30]} status={response.status_code}")
        else:
            http_failed += 1
            print(f"send failed status={response.status_code} response={response.text}")

    return DeliveryResult(
        selected=len(articles),
        preprocessing_failed=preprocessing_failed,
        backend_acknowledged=backend_acknowledged,
        http_failed=http_failed,
        transport_failed=transport_failed,
    )
