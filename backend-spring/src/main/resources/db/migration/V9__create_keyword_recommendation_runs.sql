CREATE SEQUENCE KEYWORD_RECOMMENDATION_RUN_SEQ START WITH 1 INCREMENT BY 1;

CREATE TABLE keyword_recommendation_runs (
    id NUMBER PRIMARY KEY,
    target_group_id NUMBER NOT NULL,
    status VARCHAR2(20) NOT NULL,
    active_slot NUMBER(1),
    candidate_count NUMBER,
    requested_suggestion_count NUMBER,
    saved_suggestion_count NUMBER,
    failure_code VARCHAR2(100),
    requested_by VARCHAR2(100),
    requested_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    CONSTRAINT fk_keyword_recommendation_run_group
        FOREIGN KEY (target_group_id)
        REFERENCES keyword_groups(id),
    CONSTRAINT ck_keyword_recommendation_run_status
        CHECK (status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILURE')),
    CONSTRAINT ck_keyword_recommendation_run_active
        CHECK ((status IN ('PENDING', 'RUNNING') AND active_slot = 1)
            OR (status IN ('SUCCESS', 'FAILURE') AND active_slot IS NULL)),
    CONSTRAINT ck_keyword_recommendation_run_counts
        CHECK ((candidate_count IS NULL OR candidate_count >= 0)
            AND (requested_suggestion_count IS NULL OR requested_suggestion_count >= 0)
            AND (saved_suggestion_count IS NULL OR saved_suggestion_count >= 0))
);

CREATE UNIQUE INDEX uk_keyword_recommendation_run_active
    ON keyword_recommendation_runs(active_slot);

CREATE INDEX idx_keyword_recommendation_run_group_requested
    ON keyword_recommendation_runs(target_group_id, requested_at DESC);
