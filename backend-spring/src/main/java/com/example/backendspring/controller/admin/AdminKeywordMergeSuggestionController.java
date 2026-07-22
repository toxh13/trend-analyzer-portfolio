package com.example.backendspring.controller.admin;

import com.example.backendspring.dto.KeywordMergeSuggestionResponse;
import com.example.backendspring.dto.KeywordRecommendationRunResponse;
import com.example.backendspring.entity.KeywordMergeSuggestionStatus;
import com.example.backendspring.service.KeywordRecommendationAsyncService;
import com.example.backendspring.service.KeywordRecommendationRunService;
import com.example.backendspring.service.KeywordMergeSuggestionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Locale;

/**
 * AI가 생성한 키워드 병합 추천을 검토하는 관리자 API입니다.
 *
 * <p>모델 또는 배치는 병합 후보만 제안합니다. 실제 활성 alias로 바뀌는 지점은
 * 승인 API뿐입니다.</p>
 */
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/admin/keyword-merge-suggestions")
public class AdminKeywordMergeSuggestionController {

    private final KeywordMergeSuggestionService keywordMergeSuggestionService;
    private final KeywordRecommendationRunService keywordRecommendationRunService;
    private final KeywordRecommendationAsyncService keywordRecommendationAsyncService;

    /**
     * 상태별 추천 목록을 조회합니다.
     *
     * <p>관리자 화면의 기본 검토 큐는 미처리 항목이므로 기본값은
     * {@code PENDING}입니다.</p>
     */
    @GetMapping
    public ResponseEntity<List<KeywordMergeSuggestionResponse>> getSuggestions(
            @RequestParam(required = false, defaultValue = "PENDING") String status
    ) {
        try {
            KeywordMergeSuggestionStatus parsedStatus = parseStatus(status);
            return ResponseEntity.ok(keywordMergeSuggestionService.getSuggestions(parsedStatus));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    @PostMapping("/generate")
    public ResponseEntity<KeywordRecommendationRunResponse> generateSuggestions(
            @RequestParam Long targetGroupId,
            Authentication authentication
    ) {
        String requestedBy = resolveReviewedBy(authentication);
        KeywordRecommendationRunResponse run = keywordRecommendationRunService.request(targetGroupId, requestedBy);
        keywordRecommendationAsyncService.execute(run.id());
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(run);
    }

    @GetMapping("/runs/latest")
    public ResponseEntity<KeywordRecommendationRunResponse> getLatestRun(@RequestParam Long targetGroupId) {
        KeywordRecommendationRunResponse run = keywordRecommendationRunService.getLatest(targetGroupId);
        if (run == null) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.ok(run);
    }

    /**
     * 추천을 승인하고 {@code AI_APPROVED} 출처의 활성 alias로 저장합니다.
     */
    @PatchMapping("/{suggestionId}/approve")
    public ResponseEntity<KeywordMergeSuggestionResponse> approveSuggestion(
            @PathVariable Long suggestionId,
            Authentication authentication
    ) {
        try {
            String reviewedBy = resolveReviewedBy(authentication);
            return ResponseEntity.ok(
                    keywordMergeSuggestionService.approveSuggestion(suggestionId, reviewedBy)
            );
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * 추천을 거절합니다.
     *
     * <p>거절된 원본 키워드는 같은 모델/버전 정책에서 다시 추천되지 않도록
     * 배치 단계에서 제외하는 것이 원칙입니다.</p>
     */
    @PatchMapping("/{suggestionId}/reject")
    public ResponseEntity<KeywordMergeSuggestionResponse> rejectSuggestion(
            @PathVariable Long suggestionId,
            Authentication authentication
    ) {
        try {
            String reviewedBy = resolveReviewedBy(authentication);
            return ResponseEntity.ok(
                    keywordMergeSuggestionService.rejectSuggestion(suggestionId, reviewedBy)
            );
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    private KeywordMergeSuggestionStatus parseStatus(String status) {
        if (status == null || status.isBlank()) {
            return KeywordMergeSuggestionStatus.PENDING;
        }

        return KeywordMergeSuggestionStatus.valueOf(
                status.trim().toUpperCase(Locale.ROOT)
        );
    }

    /**
     * 추후 감사 로그로 사용할 수 있도록 안정적인 검토자 식별자를 반환합니다.
     */
    private String resolveReviewedBy(Authentication authentication) {
        if (authentication == null || authentication.getName() == null || authentication.getName().isBlank()) {
            return "admin";
        }

        return authentication.getName();
    }
}
