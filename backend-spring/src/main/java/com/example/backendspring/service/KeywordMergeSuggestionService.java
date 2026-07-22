package com.example.backendspring.service;

import com.example.backendspring.dto.KeywordMergeSuggestionResponse;
import com.example.backendspring.entity.KeywordAlias;
import com.example.backendspring.entity.KeywordAliasSourceType;
import com.example.backendspring.entity.KeywordMergeSuggestion;
import com.example.backendspring.entity.KeywordMergeSuggestionStatus;
import com.example.backendspring.repository.KeywordAliasRepository;
import com.example.backendspring.repository.KeywordMergeSuggestionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * AI 키워드 병합 추천에 대한 관리자 결정을 실제 데이터에 반영하는 서비스입니다.
 *
 * <p>추천 테이블은 검토 대기열일 뿐이며 그 자체로 트렌드 동작을 바꾸지 않습니다.
 * 승인된 추천만 {@code keyword_aliases} 행을 생성하거나 재활성화합니다. 승인 후에는
 * alias 캐시를 즉시 다시 불러와 서버 재시작 없이 대시보드에 반영합니다.</p>
 */
@Service
@RequiredArgsConstructor
public class KeywordMergeSuggestionService {

    private final KeywordMergeSuggestionRepository keywordMergeSuggestionRepository;
    private final KeywordAliasRepository keywordAliasRepository;
    private final KeywordAliasCacheService keywordAliasCacheService;

    /**
     * 관리자 검토 큐에 표시할 추천 목록을 조회합니다.
     */
    @Transactional(readOnly = true)
    public List<KeywordMergeSuggestionResponse> getSuggestions(KeywordMergeSuggestionStatus status) {
        KeywordMergeSuggestionStatus searchStatus =
                status != null ? status : KeywordMergeSuggestionStatus.PENDING;

        return keywordMergeSuggestionRepository
                .findByStatusOrderBySimilarityScoreDescCreatedAtDesc(searchStatus)
                .stream()
                .map(KeywordMergeSuggestionResponse::from)
                .toList();
    }

    /**
     * 대기 중인 추천을 승인합니다.
     *
     * <p>같은 정규화 키워드를 가진 비활성 alias가 이미 있으면 새 행을 만들지 않고
     * 기존 행을 재사용합니다. 반대로 활성 alias가 이미 있으면 하나의 원본 키워드가
     * 여러 대표 키워드에 동시에 연결되는 것을 막기 위해 거부합니다.</p>
     */
    @Transactional
    public KeywordMergeSuggestionResponse approveSuggestion(Long suggestionId, String reviewedBy) {
        KeywordMergeSuggestion suggestion = findSuggestion(suggestionId);
        validatePendingSuggestion(suggestion);

        LocalDateTime now = LocalDateTime.now();

        KeywordAlias alias = keywordAliasRepository.findByNormalizedKeyword(
                        suggestion.getNormalizedSourceKeyword()
                )
                .map(existingAlias -> {
                    if (Boolean.TRUE.equals(existingAlias.getActive())) {
                        throw new IllegalArgumentException(
                                "An active alias already exists: " + existingAlias.getRawKeyword()
                        );
                    }

                    existingAlias.setKeywordGroup(suggestion.getTargetGroup());
                    existingAlias.setRawKeyword(suggestion.getSourceKeyword());
                    existingAlias.setSourceType(KeywordAliasSourceType.AI_APPROVED);
                    existingAlias.setActive(true);
                    existingAlias.setUpdatedAt(now);
                    return existingAlias;
                })
                .orElseGet(() -> KeywordAlias.builder()
                        .keywordGroup(suggestion.getTargetGroup())
                        .rawKeyword(suggestion.getSourceKeyword())
                        .normalizedKeyword(suggestion.getNormalizedSourceKeyword())
                        .sourceType(KeywordAliasSourceType.AI_APPROVED)
                        .active(true)
                        .createdAt(now)
                        .updatedAt(now)
                        .build());

        keywordAliasRepository.save(alias);

        suggestion.setStatus(KeywordMergeSuggestionStatus.APPROVED);
        suggestion.setReviewedBy(reviewedBy);
        suggestion.setReviewedAt(now);
        suggestion.setUpdatedAt(now);

        keywordAliasCacheService.reload();

        return KeywordMergeSuggestionResponse.from(suggestion);
    }

    /**
     * 대기 중인 추천을 거절하고 검토자를 기록합니다.
     *
     * <p>거절된 원본 키워드는 다음 추천 배치에서 제외해 관리자가 같은 잘못된
     * 병합 후보를 반복 검토하지 않도록 해야 합니다.</p>
     */
    @Transactional
    public KeywordMergeSuggestionResponse rejectSuggestion(Long suggestionId, String reviewedBy) {
        KeywordMergeSuggestion suggestion = findSuggestion(suggestionId);
        validatePendingSuggestion(suggestion);

        LocalDateTime now = LocalDateTime.now();

        suggestion.setStatus(KeywordMergeSuggestionStatus.REJECTED);
        suggestion.setReviewedBy(reviewedBy);
        suggestion.setReviewedAt(now);
        suggestion.setUpdatedAt(now);

        return KeywordMergeSuggestionResponse.from(suggestion);
    }

    private KeywordMergeSuggestion findSuggestion(Long suggestionId) {
        return keywordMergeSuggestionRepository.findById(suggestionId)
                .orElseThrow(() -> new IllegalArgumentException("Suggestion not found. id=" + suggestionId));
    }

    private void validatePendingSuggestion(KeywordMergeSuggestion suggestion) {
        if (suggestion.getStatus() != KeywordMergeSuggestionStatus.PENDING) {
            throw new IllegalArgumentException("Suggestion was already reviewed.");
        }
    }
}
