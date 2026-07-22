-- 최소 관리자 페이지용 키워드 관리 테이블
-- 현재 단계에서는 API 로그/회원관리/기사관리 테이블을 만들지 않고,
-- 운영 키워드 등록 및 활성/비활성 관리에 필요한 구조만 추가합니다.
CREATE TABLE crawler_keywords (
    id NUMBER PRIMARY KEY,
    keyword VARCHAR2(100) NOT NULL UNIQUE,
    category VARCHAR2(100),
    active NUMBER(1) DEFAULT 1 NOT NULL,
    priority NUMBER DEFAULT 0 NOT NULL,
    notion_enabled NUMBER(1) DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE SEQUENCE CRAWLER_KEYWORD_SEQ START WITH 1 INCREMENT BY 1;
