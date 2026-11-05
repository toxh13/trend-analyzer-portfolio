-- ============================================================
-- v2 파이프라인 실버·운영 테이블
-- 기사(news_articles), 기사 키워드(news_keywords), 키워드 규칙 버전,
-- 실행 기록(pipeline_runs, pipeline_feed_runs), 삭제 요청 차단 목록을 만듭니다.
-- v1 테이블(articles, article_keywords, crawl_batch_runs 등)은 그대로 두며 계획 3에서 삭제합니다.
-- 모든 TIMESTAMP 열은 UTC 값을 저장합니다.
-- 기사·키워드·실행 기록 쓰기는 파이프라인만 합니다.
-- ============================================================

CREATE SEQUENCE NEWS_ARTICLE_SEQ START WITH 1 INCREMENT BY 1;

CREATE TABLE news_articles (
    id NUMBER DEFAULT NEWS_ARTICLE_SEQ.NEXTVAL NOT NULL,
    source VARCHAR2(10) NOT NULL,
    -- 매체 기사 번호. 번호를 못 뽑으면 정규화한 링크 URL이 들어가므로 링크만큼 길게 둡니다.
    source_article_id VARCHAR2(1000 CHAR) NOT NULL,
    category VARCHAR2(20 CHAR) NOT NULL,
    title VARCHAR2(1000 CHAR) NOT NULL,
    -- 요약이 없으면 NULL (Oracle은 빈 문자열을 NULL로 저장합니다)
    summary CLOB,
    link VARCHAR2(1000 CHAR) NOT NULL,
    published_at TIMESTAMP NOT NULL,
    -- 이 기사를 처음 적재한 실행의 구간 끝. 다시 실행해도 바뀌지 않습니다.
    first_seen_run_end TIMESTAMP NOT NULL,

    CONSTRAINT pk_news_articles PRIMARY KEY (id),
    CONSTRAINT uk_news_articles_source_article UNIQUE (source, source_article_id),
    CONSTRAINT ck_news_articles_source CHECK (source IN ('yna', 'khan', 'donga')),
    CONSTRAINT ck_news_articles_category CHECK (
        category IN ('정치', '경제', '사회', '세계', '문화', 'IT/과학')
    )
);

CREATE TABLE news_keywords (
    article_id NUMBER NOT NULL,
    keyword VARCHAR2(255 CHAR) NOT NULL,
    rule_version VARCHAR2(8) NOT NULL,

    -- 파이프라인은 (기사, 규칙 버전) 단위로 지우고 다시 씁니다.
    CONSTRAINT pk_news_keywords PRIMARY KEY (article_id, keyword, rule_version),
    CONSTRAINT fk_news_keywords_article FOREIGN KEY (article_id)
        REFERENCES news_articles (id)
);

CREATE TABLE keyword_rule_versions (
    -- 규칙 파일 정규화 JSON의 sha256 앞 8자리
    rule_version VARCHAR2(8) NOT NULL,
    rule_json CLOB NOT NULL,
    status VARCHAR2(10) NOT NULL,
    created_at TIMESTAMP DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,

    CONSTRAINT pk_keyword_rule_versions PRIMARY KEY (rule_version),
    CONSTRAINT ck_keyword_rule_versions_status CHECK (status IN ('BUILDING', 'ACTIVE', 'RETIRED'))
);

-- ACTIVE는 한 버전만: ACTIVE 행만 1을 갖고 나머지는 NULL이라 유니크 인덱스에 들어가지 않습니다.
CREATE UNIQUE INDEX uk_keyword_rule_versions_active
    ON keyword_rule_versions (CASE WHEN status = 'ACTIVE' THEN 1 END);

CREATE TABLE pipeline_runs (
    -- uuid5(DAG id + 구간 끝): 같은 구간을 다시 실행하면 같은 값이라 같은 행을 갱신합니다.
    run_id VARCHAR2(36) NOT NULL,
    interval_end TIMESTAMP NOT NULL,
    run_type VARCHAR2(20) NOT NULL,
    outcome VARCHAR2(30) NOT NULL,
    feed_count NUMBER NOT NULL,
    failed_feed_count NUMBER NOT NULL,
    -- 기사 건수는 서로 다른 기사 기준 (한 실행의 두 피드에 나온 기사는 한 번만 셉니다)
    new_articles NUMBER NOT NULL,
    existing_articles NUMBER NOT NULL,
    excluded_notice NUMBER NOT NULL,
    excluded_blocklist NUMBER NOT NULL,
    parse_failed NUMBER NOT NULL,
    keyword_rows NUMBER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,

    CONSTRAINT pk_pipeline_runs PRIMARY KEY (run_id),
    CONSTRAINT ck_pipeline_runs_run_type CHECK (run_type IN ('scheduled', 'backfill', 'manual')),
    CONSTRAINT ck_pipeline_runs_outcome CHECK (
        outcome IN ('SUCCESS', 'EMPTY', 'PARTIAL_FAILURE', 'FAILURE')
    ),
    CONSTRAINT ck_pipeline_runs_counts CHECK (
        feed_count >= 0 AND failed_feed_count >= 0 AND failed_feed_count <= feed_count
        AND new_articles >= 0 AND existing_articles >= 0
        AND excluded_notice >= 0 AND excluded_blocklist >= 0
        AND parse_failed >= 0 AND keyword_rows >= 0
    ),
    CONSTRAINT ck_pipeline_runs_time CHECK (completed_at >= started_at)
);

CREATE TABLE pipeline_feed_runs (
    run_id VARCHAR2(36) NOT NULL,
    source VARCHAR2(10) NOT NULL,
    feed VARCHAR2(50) NOT NULL,
    -- 응답을 받지 못한 실패 피드는 NULL
    http_status NUMBER(3),
    etag VARCHAR2(1000),
    last_modified VARCHAR2(1000),
    raw_key VARCHAR2(400),
    -- 파싱된 항목 수. 파싱 실패(parse_failed)는 파싱 단계에서 이미 빠져 여기에 들어가지 않습니다.
    item_count NUMBER NOT NULL,
    new_articles NUMBER NOT NULL,
    existing_articles NUMBER NOT NULL,
    excluded_notice NUMBER NOT NULL,
    excluded_blocklist NUMBER NOT NULL,
    parse_failed NUMBER NOT NULL,
    -- DuckDB 품질 검사 결과 (기록용)
    missing_required NUMBER NOT NULL,
    duplicate_keys NUMBER NOT NULL,
    error VARCHAR2(4000 CHAR),

    CONSTRAINT fk_pipeline_feed_runs_run FOREIGN KEY (run_id)
        REFERENCES pipeline_runs (run_id),
    CONSTRAINT uk_pipeline_feed_runs_feed UNIQUE (run_id, source, feed),
    CONSTRAINT ck_pipeline_feed_runs_counts CHECK (
        item_count >= 0 AND new_articles >= 0 AND existing_articles >= 0
        AND excluded_notice >= 0 AND excluded_blocklist >= 0 AND parse_failed >= 0
        AND missing_required >= 0 AND duplicate_keys >= 0
    ),
    -- 항목마다 한 칸에만 셉니다. 같은 실행의 앞 피드가 가져간 기사는 existing_articles에 들어갑니다.
    CONSTRAINT ck_pipeline_feed_runs_reconcile CHECK (
        item_count = new_articles + existing_articles + excluded_notice + excluded_blocklist
    )
);

CREATE TABLE article_blocklist (
    source VARCHAR2(10) NOT NULL,
    source_article_id VARCHAR2(1000 CHAR) NOT NULL,
    requested_at TIMESTAMP DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,
    reason VARCHAR2(1000 CHAR),
    requester_type VARCHAR2(30) NOT NULL,

    -- 처리 단계가 항상 이 목록을 걸러내므로 다시 처리해도 기사가 살아나지 않습니다.
    CONSTRAINT pk_article_blocklist PRIMARY KEY (source, source_article_id)
);
