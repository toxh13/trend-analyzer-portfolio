package com.example.backendspring.repository;

import com.example.backendspring.entity.KeywordMergeSuggestion;
import com.example.backendspring.entity.KeywordMergeSuggestionStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface KeywordMergeSuggestionRepository extends JpaRepository<KeywordMergeSuggestion, Long> {

    /**
     * 관리자 추천 검토 화면에 표시할 목록을 조회합니다.
     *
     * <p>유사도 점수가 높은 추천을 먼저 보여주고, 점수가 같으면 더 최근에
     * 생성된 추천을 우선합니다.</p>
     */
    List<KeywordMergeSuggestion> findByStatusOrderBySimilarityScoreDescCreatedAtDesc(
            KeywordMergeSuggestionStatus status
    );

    /**
     * 원본 키워드가 이미 승인 또는 거절된 적이 있는지 확인합니다.
     *
     * <p>Python 추천 배치는 이 조회를 사용해 이미 처리된 키워드를 다시
     * 추천하지 않도록 해야 합니다.</p>
     */
    boolean existsByNormalizedSourceKeywordAndTargetGroupIdAndStatusIn(
            String normalizedSourceKeyword,
            Long targetGroupId,
            Collection<KeywordMergeSuggestionStatus> statuses
    );

    boolean existsByNormalizedSourceKeywordAndTargetGroupIdAndModelVersion(
            String normalizedSourceKeyword,
            Long targetGroupId,
            String modelVersion
    );
}
