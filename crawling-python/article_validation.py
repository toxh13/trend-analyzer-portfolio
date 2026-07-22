def find_invalid_article_reason(article: dict) -> str | None:
    """백엔드 전송 전에 분석용 기사로 사용할 수 없는 이유를 반환합니다."""
    required_fields = {
        "title": "missing_title",
        "sourceUrl": "missing_source_url",
        "source": "missing_source",
        "category": "missing_category",
        "publishedAt": "missing_published_at",
    }
    for field, reason in required_fields.items():
        value = article.get(field)
        if value is None or not str(value).strip():
            return reason

    content = article.get("content")
    if content is None or not str(content).strip():
        return "missing_content"
    return None
