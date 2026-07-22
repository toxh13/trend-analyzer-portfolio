-- 관리자 키워드의 용도를 구분하기 위한 컬럼입니다.
-- TRACKING: 추적/보고서 반영 대상 키워드
-- BLOCKED : 의미 없는 키워드로 저장/집계에서 제외할 키워드

ALTER TABLE crawler_keywords
ADD keyword_type VARCHAR2(30) DEFAULT 'TRACKING' NOT NULL;