import unittest

from article_validation import find_invalid_article_reason


class ArticleValidationTest(unittest.TestCase):
    def setUp(self):
        self.article = {
            "title": "테스트 기사",
            "content": "분석에 사용할 수 있는 정상 본문입니다.",
            "sourceUrl": "https://example.com/article",
            "source": "테스트 언론사",
            "category": "IT/과학",
            "publishedAt": "2026-07-19T12:00:00",
        }

    def test_accepts_article_with_required_analysis_fields(self):
        self.assertIsNone(find_invalid_article_reason(self.article))

    def test_rejects_article_without_original_published_time(self):
        self.article["publishedAt"] = None
        self.assertEqual(find_invalid_article_reason(self.article), "missing_published_at")

    def test_rejects_article_without_content(self):
        self.article["content"] = None
        self.assertEqual(find_invalid_article_reason(self.article), "missing_content")


if __name__ == "__main__":
    unittest.main()
