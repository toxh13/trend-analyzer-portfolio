-- ============================================================
-- 키워드 병합 추천 기능 테이블 생성
-- 기준 키워드(keyword_groups), 승인 alias(keyword_aliases),
-- AI 추천 후보(keyword_merge_suggestions)를 분리합니다.
-- ============================================================

CREATE SEQUENCE KEYWORD_GROUP_SEQ START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE KEYWORD_ALIAS_SEQ START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE KEYWORD_MERGE_SUGGESTION_SEQ START WITH 1 INCREMENT BY 1;

CREATE TABLE keyword_groups (
    id NUMBER PRIMARY KEY,
    canonical_keyword VARCHAR2(100) NOT NULL,
    normalized_canonical_keyword VARCHAR2(100) NOT NULL,
    description VARCHAR2(500),
    active NUMBER(1) DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT uk_keyword_groups_normalized
        UNIQUE (normalized_canonical_keyword)
);

CREATE TABLE keyword_aliases (
    id NUMBER PRIMARY KEY,
    keyword_group_id NUMBER NOT NULL,
    raw_keyword VARCHAR2(100) NOT NULL,
    normalized_keyword VARCHAR2(100) NOT NULL,
    source_type VARCHAR2(30) DEFAULT 'ADMIN' NOT NULL,
    active NUMBER(1) DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT fk_keyword_alias_group
        FOREIGN KEY (keyword_group_id)
        REFERENCES keyword_groups(id),

    -- 같은 alias가 여러 대표 키워드에 동시에 붙으면 집계가 꼬이므로 전역 unique로 둡니다.
    CONSTRAINT uk_keyword_aliases_normalized
        UNIQUE (normalized_keyword)
);

CREATE TABLE keyword_merge_suggestions (
    id NUMBER PRIMARY KEY,
    source_keyword VARCHAR2(100) NOT NULL,
    normalized_source_keyword VARCHAR2(100) NOT NULL,
    target_group_id NUMBER NOT NULL,
    target_keyword VARCHAR2(100) NOT NULL,
    similarity_score NUMBER(5, 4) NOT NULL,
    reason VARCHAR2(1000),
    status VARCHAR2(30) DEFAULT 'PENDING' NOT NULL,
    model_name VARCHAR2(200),
    model_version VARCHAR2(100),
    reviewed_by VARCHAR2(100),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT fk_keyword_suggestion_group
        FOREIGN KEY (target_group_id)
        REFERENCES keyword_groups(id),

    -- 같은 모델 버전에서 같은 원본 키워드가 같은 그룹으로 중복 추천되는 것을 방지합니다.
    CONSTRAINT uk_keyword_merge_suggestion_unique
        UNIQUE (normalized_source_keyword, target_group_id, model_version)
);