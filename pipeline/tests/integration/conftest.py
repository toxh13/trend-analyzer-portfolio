"""통합 테스트 공용 준비: Oracle Free 컨테이너, Flyway 마이그레이션 적용, 테스트마다 v2 테이블 비우기.

Docker가 꺼져 있으면 건너뛰지 않고 실패한다(멱등성 검증이 조용히 빠지지 않게).
"""

import os
import re
import secrets
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import oracledb
import pytest
from testcontainers.community.oracle import OracleDbContainer

from trend_pipeline.article_key import article_key, display_link
from trend_pipeline.envelope import build_envelope, to_bytes
from trend_pipeline.feeds import FeedSpec, load_feeds
from trend_pipeline.keys import raw_key
from trend_pipeline.keywords import RuleSet, extract_keywords, load_rules
from trend_pipeline.load import FeedOutcome, LoadItem, RunLoadInput, ensure_rule_version, writable_rule_sets
from trend_pipeline.parse import parse_feed
from trend_pipeline.quality import check_items
from trend_pipeline.raw_store import LocalRawStore
from trend_pipeline.text_clean import clean_summary, clean_title

IMAGE = "gvenzl/oracle-free:23-slim"
SERVICE = "FREEPDB1"
APP_USER = "trend_test"
REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "backend-spring" / "src" / "main" / "resources" / "db" / "migration"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "feeds"
ENV_VARS = ("ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD")

# 자식 테이블이 먼저 오는 순서(FK 때문에 이 순서로 비운다)
V2_TABLES = (
    "pipeline_feed_runs",
    "pipeline_runs",
    "news_keywords",
    "news_article_categories",
    "news_articles",
    "article_blocklist",
    "keyword_rule_versions",
)

INTERVAL_END = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class DbParams:
    dsn: str
    user: str
    password: str

    def connect(self) -> oracledb.Connection:
        return oracledb.connect(user=self.user, password=self.password, dsn=self.dsn)


def _password() -> str:
    # 실행할 때마다 새로 만든다(저장소에 비밀번호를 두지 않는다). 영문자로 시작하는 영숫자만 쓴다
    return "Tp" + secrets.token_hex(12)


def migration_files() -> list[Path]:
    """V{번호}__*.sql 을 번호(숫자) 순서로. 문자열 정렬이면 V10이 V2 앞에 온다."""
    files = []
    for path in MIGRATIONS.glob("V*.sql"):
        match = re.match(r"V(\d+)__", path.name)
        if match is None:
            raise ValueError(f"마이그레이션 파일 이름 형식이 아니다: {path.name}")
        files.append((int(match.group(1)), path))
    return [path for _, path in sorted(files)]


def _statements(sql: str) -> list[str]:
    """';' 단위로 자른다. 이 폴더에는 PL/SQL 블록이 없다. 주석만 남은 조각은 버린다."""
    statements = []
    for chunk in sql.split(";"):
        code = "\n".join(line for line in chunk.splitlines() if not line.strip().startswith("--")).strip()
        if code:
            statements.append(code)
    return statements


def apply_migrations(conn: oracledb.Connection) -> None:
    with conn.cursor() as cursor:
        for path in migration_files():
            for statement in _statements(path.read_text(encoding="utf-8")):
                try:
                    cursor.execute(statement)
                except oracledb.Error as exc:
                    raise RuntimeError(f"{path.name} 적용 실패: {exc}\n--- 문장 ---\n{statement}") from exc
    conn.commit()


@pytest.fixture(scope="session")
def db_params() -> Iterator[DbParams]:
    """세션당 한 번 Oracle 컨테이너를 띄우고 앱 계정으로 마이그레이션을 적용한다. 세 환경 변수도 이 동안 설정한다."""
    password = _password()
    # oracle_password를 직접 넘긴다. 넘기지 않으면 testcontainers가 환경 변수 ORACLE_PASSWORD를 SYS 비밀번호로 읽는다
    container = OracleDbContainer(IMAGE, oracle_password=_password(), username=APP_USER, password=password)
    saved = {name: os.environ.get(name) for name in ENV_VARS}
    try:
        with warnings.catch_warnings():
            # testcontainers 4.15의 OracleDbContainer가 내부에서 문자열 조건의 wait_for_logs를 써서 내는 경고만 끈다
            warnings.filterwarnings(
                "ignore",
                message="The wait_for_logs function with string or callable predicates is deprecated",
                category=DeprecationWarning,
            )
            container.start()  # 준비 대기 중 실패해도 아래 finally가 컨테이너를 지운다
        host = container.get_container_host_ip()
        port = container.get_exposed_port(1521)
        params = DbParams(dsn=f"{host}:{port}/{SERVICE}", user=APP_USER, password=password)
        with params.connect() as conn:
            apply_migrations(conn)
        os.environ.update({"ORACLE_DSN": params.dsn, "ORACLE_USER": params.user, "ORACLE_PASSWORD": params.password})
        yield params
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        container.stop()


def empty_v2_tables(conn: oracledb.Connection) -> None:
    with conn.cursor() as cursor:
        for table in V2_TABLES:
            cursor.execute(f"DELETE FROM {table}")
    conn.commit()


@pytest.fixture
def conn(db_params: DbParams) -> Iterator[oracledb.Connection]:
    """테스트마다 새 연결. v2 테이블을 비운 상태에서 시작한다."""
    connection = db_params.connect()
    try:
        empty_v2_tables(connection)
        yield connection
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture(scope="session")
def rule_set() -> RuleSet:
    """패키지 규칙. Kiwi를 한 번 미리 만들어 둔다(지연 생성 캐시에 잠금이 없어 동시성 테스트 전에 데운다)."""
    rules = load_rules()
    extract_keywords("정부 예산안 국회 통과", rules)
    return rules


@pytest.fixture
def rules(conn: oracledb.Connection, rule_set: RuleSet) -> dict[str, RuleSet]:
    """처리 작업(Task 12)과 같은 방식: 규칙 버전을 등록한 뒤 쓰기 가능한 규칙을 DB에서 읽는다."""
    ensure_rule_version(conn, rule_set)
    return writable_rule_sets(conn)


def feed_spec(source: str, category: str) -> FeedSpec:
    """고정 샘플 파일은 (매체, 카테고리)로 feeds.yml 피드에 대응시킨다 (예: khan_politics.xml → khan/politic_news)."""
    return next(spec for spec in load_feeds() if spec.source == source and spec.category == category)


def load_items(spec: FeedSpec, xml: str, interval_end: datetime = INTERVAL_END) -> tuple[list[LoadItem], FeedOutcome]:
    """피드 본문 하나를 처리 작업(Task 12)과 같은 방식으로 LoadItem 목록과 FeedOutcome으로 바꾼다."""
    env = build_envelope(spec, interval_end, 200, {"ETag": '"fixture-etag"'}, xml.encode("utf-8"))
    parsed = parse_feed(env)
    keyed = [(article_key(spec.source, item.link, item.guid), item) for item in parsed.items]
    items = [
        LoadItem(
            feed=spec,
            key=key,
            title=item.title,
            summary=clean_summary(item.summary),
            link=display_link(spec.source, item.link, item.guid),
            published_at=item.published_at,
            title_excluded=clean_title(item.title).excluded,
        )
        for key, item in keyed
    ]
    quality = check_items(keyed)
    outcome = FeedOutcome(
        feed=spec,
        status=200,
        etag=env.etag,
        last_modified=env.last_modified,
        raw_key=raw_key(interval_end, spec.source, spec.feed),
        fetched_at=env.requested_at,
        item_count=len(items),
        parse_failed=parsed.parse_failed,
        missing_required=quality.missing_required,
        duplicate_keys=quality.duplicate_keys,
        error=None,
    )
    return items, outcome


@pytest.fixture(scope="session")
def sample_run() -> RunLoadInput:
    """고정 샘플 2개(연합 정치 120건, 경향 정치 50건)로 만든 한 실행. feeds.yml 순서대로 둔다."""
    items: list[LoadItem] = []
    outcomes: list[FeedOutcome] = []
    for name, source in (("yna_politics.xml", "yna"), ("khan_politics.xml", "khan")):
        feed_items, outcome = load_items(feed_spec(source, "정치"), (FIXTURES / name).read_text(encoding="utf-8"))
        items.extend(feed_items)
        outcomes.append(outcome)
    return RunLoadInput(interval_end=INTERVAL_END, run_type="scheduled", items=items, feeds=outcomes)


# 경향 고정 샘플 파일 이름은 feeds.yml의 피드 id와 다르다. 나머지 매체는 파일 이름 = 피드 id
KHAN_FIXTURE_FEEDS = {
    "politics": "politic_news",
    "economy": "economy_news",
    "society": "society_news",
    "world": "kh_world",
    "culture": "culture_news",
    "science": "science_news",
}


def fixture_feed_xml() -> dict[tuple[str, str], str]:
    """고정 샘플 17개를 (source, feed) 키로 읽는다."""
    result: dict[tuple[str, str], str] = {}
    for path in sorted(FIXTURES.glob("*.xml")):
        source, section = path.stem.split("_", 1)
        feed = KHAN_FIXTURE_FEEDS[section] if source == "khan" else section
        result[(source, feed)] = path.read_text(encoding="utf-8")
    return result


@pytest.fixture
def store(tmp_path: Path) -> LocalRawStore:
    """비어 있는 로컬 원본 저장소."""
    return LocalRawStore(tmp_path / "raw-store")


@pytest.fixture
def seeded_store(store: LocalRawStore) -> LocalRawStore:
    """INTERVAL_END 구간의 17개 피드를 고정 샘플로 채운 원본 저장소(feeds.yml의 모든 피드)."""
    xml_by_feed = fixture_feed_xml()
    for spec in load_feeds():
        xml = xml_by_feed[(spec.source, spec.feed)]
        env = build_envelope(spec, INTERVAL_END, 200, {"ETag": '"fixture-etag"'}, xml.encode("utf-8"))
        assert store.put_if_absent(raw_key(INTERVAL_END, spec.source, spec.feed), to_bytes(env))
    return store
