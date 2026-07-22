-- trend_metrics는 원본 데이터가 아니라 매시간 다시 생성되는 최신 집계 스냅샷이다.
-- 기존 중복이 있다면 같은 keyword/category 조합에서 가장 최근 id 한 건만 남긴다.
DELETE FROM trend_metrics
WHERE id NOT IN (
    SELECT MAX(id)
    FROM trend_metrics
    GROUP BY keyword, category
);

ALTER TABLE trend_metrics
    ADD CONSTRAINT uk_trend_metrics_keyword_category UNIQUE (keyword, category);
