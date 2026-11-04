import re


def test_package_imports_with_version():
    import trend_pipeline

    # 버전은 pyproject.toml의 값을 설치 메타데이터로 읽어 온다 (Task 3의 CRAWLER_VERSION 출처)
    assert re.fullmatch(r"\d+\.\d+\.\d+", trend_pipeline.__version__)


def test_integration_marker_is_registered(pytestconfig):
    markers = pytestconfig.getini("markers")
    assert any(marker.startswith("integration:") for marker in markers)
