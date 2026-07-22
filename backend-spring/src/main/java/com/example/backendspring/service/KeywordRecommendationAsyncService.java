package com.example.backendspring.service;

import com.example.backendspring.dto.KeywordRecommendationResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
@Slf4j
public class KeywordRecommendationAsyncService {

    private final KeywordRecommendationRunService keywordRecommendationRunService;
    private final KeywordMergeSuggestionBatchService keywordMergeSuggestionBatchService;

    @Async("keywordRecommendationExecutor")
    public void execute(Long runId) {
        try {
            KeywordRecommendationRunService.RecommendationRunContext context = keywordRecommendationRunService.markRunning(runId);
            KeywordMergeSuggestionBatchService.CandidateSelection candidates =
                    keywordMergeSuggestionBatchService.loadCandidateKeywords(context.targetGroupId(), context.targetKeyword());
            if (candidates.candidates().isEmpty()) {
                keywordRecommendationRunService.completeSuccess(runId, 0, 0, 0);
                return;
            }
            KeywordRecommendationResponse response = keywordMergeSuggestionBatchService.requestRecommendations(candidates);
            int savedSuggestionCount = keywordMergeSuggestionBatchService.saveRecommendations(response);
            int requestedSuggestionCount = response.suggestions() == null ? 0 : response.suggestions().size();
            keywordRecommendationRunService.completeSuccess(
                    runId,
                    candidates.candidates().size(),
                    requestedSuggestionCount,
                    savedSuggestionCount
            );
        } catch (Exception error) {
            log.warn("Keyword recommendation run {} failed", runId, error);
            try {
                keywordRecommendationRunService.completeFailure(runId, failureCode(error));
            } catch (Exception completionError) {
                log.error("Failed to mark keyword recommendation run {} as failed", runId, completionError);
            }
        }
    }

    private String failureCode(Exception error) {
        if (error instanceof IllegalArgumentException) {
            return "INVALID_INPUT";
        }
        if (error.getCause() instanceof org.springframework.web.client.RestClientException) {
            return "RECOMMENDER_UNAVAILABLE";
        }
        return "RECOMMENDATION_FAILED";
    }
}
