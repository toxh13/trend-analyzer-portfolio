import unittest
from unittest.mock import patch

from nlp.keyword_extractor import keyword_extractor


class KeywordExtractorTest(unittest.TestCase):
    @patch("nlp.keyword_extractor.OKT.nouns")
    def test_returns_keyword_with_occurrence_count(self, nouns):
        nouns.return_value = ["인공지능", "반도체", "인공지능", "인공지능", "기자", "AI"]

        result = keyword_extractor("테스트 본문", top_n=2)

        self.assertEqual(
            result,
            [
                {"keyword": "인공지능", "occurrenceCount": 3},
                {"keyword": "반도체", "occurrenceCount": 1},
            ],
        )


if __name__ == "__main__":
    unittest.main()
