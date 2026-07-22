CREATE SEQUENCE CRAWL_BATCH_RUN_SEQ START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE CRAWL_CHANNEL_RUN_SEQ START WITH 1 INCREMENT BY 1;

CREATE TABLE crawl_batch_runs (
    id NUMBER PRIMARY KEY,
    run_id VARCHAR2(36) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    outcome VARCHAR2(30) NOT NULL,
    crawler_output_count NUMBER NOT NULL,
    source_invalid_count NUMBER NOT NULL,
    validation_rejected_count NUMBER NOT NULL,
    duplicate_url_count NUMBER NOT NULL,
    eligible_count NUMBER NOT NULL,
    selected_count NUMBER NOT NULL,
    dropped_by_limit_count NUMBER NOT NULL,
    preprocessing_failed_count NUMBER NOT NULL,
    backend_acknowledged_count NUMBER NOT NULL,
    http_failed_count NUMBER NOT NULL,
    transport_failed_count NUMBER NOT NULL,
    successful_channel_count NUMBER NOT NULL,
    partial_channel_count NUMBER NOT NULL,
    empty_channel_count NUMBER NOT NULL,
    failed_channel_count NUMBER NOT NULL,
    successful_unit_count NUMBER NOT NULL,
    partial_unit_count NUMBER NOT NULL,
    empty_unit_count NUMBER NOT NULL,
    failed_unit_count NUMBER NOT NULL,
    duration_ms NUMBER NOT NULL,
    created_at TIMESTAMP DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,

    CONSTRAINT uk_crawl_batch_runs_run_id UNIQUE (run_id),
    CONSTRAINT ck_crawl_batch_runs_outcome CHECK (
        outcome IN ('RUNNING', 'SUCCESS', 'EMPTY', 'PARTIAL_FAILURE', 'FAILURE')
    ),
    CONSTRAINT ck_crawl_batch_runs_time CHECK (
        (outcome = 'RUNNING' AND completed_at IS NULL)
        OR (outcome <> 'RUNNING' AND completed_at IS NOT NULL AND completed_at >= started_at)
    ),
    CONSTRAINT ck_crawl_batch_runs_counts CHECK (
        crawler_output_count >= 0 AND source_invalid_count >= 0
        AND validation_rejected_count >= 0 AND duplicate_url_count >= 0
        AND eligible_count >= 0 AND selected_count >= 0
        AND dropped_by_limit_count >= 0 AND preprocessing_failed_count >= 0
        AND backend_acknowledged_count >= 0 AND http_failed_count >= 0
        AND transport_failed_count >= 0 AND successful_channel_count >= 0
        AND partial_channel_count >= 0 AND empty_channel_count >= 0
        AND failed_channel_count >= 0 AND successful_unit_count >= 0
        AND partial_unit_count >= 0 AND empty_unit_count >= 0
        AND failed_unit_count >= 0 AND duration_ms >= 0
    ),
    CONSTRAINT ck_crawl_batch_runs_reconcile CHECK (
        (outcome = 'RUNNING'
            AND crawler_output_count = 0 AND source_invalid_count = 0
            AND validation_rejected_count = 0 AND duplicate_url_count = 0
            AND eligible_count = 0 AND selected_count = 0 AND dropped_by_limit_count = 0
            AND preprocessing_failed_count = 0 AND backend_acknowledged_count = 0
            AND http_failed_count = 0 AND transport_failed_count = 0
            AND successful_channel_count = 0 AND partial_channel_count = 0
            AND empty_channel_count = 0 AND failed_channel_count = 0
            AND successful_unit_count = 0 AND partial_unit_count = 0
            AND empty_unit_count = 0 AND failed_unit_count = 0 AND duration_ms = 0)
        OR (outcome <> 'RUNNING'
            AND crawler_output_count = validation_rejected_count + duplicate_url_count + eligible_count
            AND eligible_count = selected_count + dropped_by_limit_count
            AND selected_count = preprocessing_failed_count + backend_acknowledged_count
                + http_failed_count + transport_failed_count
            AND successful_channel_count + partial_channel_count
                + empty_channel_count + failed_channel_count = 3)
    )
);

CREATE INDEX idx_crawl_batch_runs_started_at ON crawl_batch_runs (started_at);

CREATE TABLE crawl_channel_runs (
    id NUMBER PRIMARY KEY,
    batch_run_id NUMBER NOT NULL,
    channel VARCHAR2(20) NOT NULL,
    outcome VARCHAR2(30) NOT NULL,
    validated_article_count NUMBER NOT NULL,
    source_invalid_count NUMBER NOT NULL,
    successful_units NUMBER NOT NULL,
    partial_units NUMBER NOT NULL,
    empty_units NUMBER NOT NULL,
    failed_units NUMBER NOT NULL,

    CONSTRAINT fk_crawl_channel_run_batch FOREIGN KEY (batch_run_id)
        REFERENCES crawl_batch_runs(id),
    CONSTRAINT uk_crawl_channel_run_channel UNIQUE (batch_run_id, channel),
    CONSTRAINT ck_crawl_channel_run_name CHECK (channel IN ('naver', 'daum', 'rss')),
    CONSTRAINT ck_crawl_channel_run_outcome CHECK (
        outcome IN ('SUCCESS', 'EMPTY', 'PARTIAL_FAILURE', 'FAILURE')
    ),
    CONSTRAINT ck_crawl_channel_run_counts CHECK (
        validated_article_count >= 0 AND source_invalid_count >= 0
        AND successful_units >= 0 AND partial_units >= 0
        AND empty_units >= 0 AND failed_units >= 0
    )
);
