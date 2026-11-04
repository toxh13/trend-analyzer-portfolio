"""Trend Analyzer v2 파이프라인: RSS 수집 -> 원본 봉투 -> Oracle silver 적재."""

from importlib.metadata import version

# 버전의 유일한 출처는 pyproject.toml이다. 설치 메타데이터에서 읽는다.
__version__ = version("trend-pipeline")
