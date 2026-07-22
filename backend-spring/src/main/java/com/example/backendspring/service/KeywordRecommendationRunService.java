package com.example.backendspring.service;

import com.example.backendspring.dto.KeywordRecommendationRunResponse;
import com.example.backendspring.entity.KeywordGroup;
import com.example.backendspring.entity.KeywordRecommendationRun;
import com.example.backendspring.entity.KeywordRecommendationRunStatus;
import com.example.backendspring.repository.KeywordGroupRepository;
import com.example.backendspring.repository.KeywordRecommendationRunRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;

@Service
@RequiredArgsConstructor
public class KeywordRecommendationRunService {

    private static final int ACTIVE_SLOT = 1;
    private static final long STALE_RUN_MINUTES = 10;

    private final KeywordRecommendationRunRepository keywordRecommendationRunRepository;
    private final KeywordGroupRepository keywordGroupRepository;

    @Transactional
    public KeywordRecommendationRunResponse request(Long targetGroupId, String requestedBy) {
        keywordRecommendationRunRepository.findFirstByActiveSlotOrderByRequestedAtDesc(ACTIVE_SLOT)
                .ifPresent(activeRun -> {
                    if (!recoverIfStale(activeRun)) {
                        throw new ResponseStatusException(HttpStatus.CONFLICT, "An AI recommendation job is already running.");
                    }
                });

        KeywordGroup targetGroup = keywordGroupRepository.findById(targetGroupId)
                .filter(group -> Boolean.TRUE.equals(group.getActive()))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "Active target keyword group not found."));

        KeywordRecommendationRun run = KeywordRecommendationRun.builder()
                .targetGroup(targetGroup)
                .status(KeywordRecommendationRunStatus.PENDING)
                .activeSlot(ACTIVE_SLOT)
                .requestedBy(requestedBy)
                .requestedAt(LocalDateTime.now())
                .build();
        try {
            return KeywordRecommendationRunResponse.from(keywordRecommendationRunRepository.saveAndFlush(run));
        } catch (DataIntegrityViolationException error) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "An AI recommendation job is already running.", error);
        }
    }

    @Transactional
    public RecommendationRunContext markRunning(Long runId) {
        KeywordRecommendationRun run = findRun(runId);
        if (run.getStatus() != KeywordRecommendationRunStatus.PENDING) {
            throw new IllegalStateException("Recommendation run is not pending.");
        }

        run.setStatus(KeywordRecommendationRunStatus.RUNNING);
        run.setStartedAt(LocalDateTime.now());
        return new RecommendationRunContext(run.getId(), run.getTargetGroup().getId(), run.getTargetGroup().getCanonicalKeyword());
    }

    @Transactional
    public void completeSuccess(Long runId, int candidateCount, int requestedSuggestionCount, int savedSuggestionCount) {
        KeywordRecommendationRun run = findRun(runId);
        run.setStatus(KeywordRecommendationRunStatus.SUCCESS);
        run.setActiveSlot(null);
        run.setCandidateCount(candidateCount);
        run.setRequestedSuggestionCount(requestedSuggestionCount);
        run.setSavedSuggestionCount(savedSuggestionCount);
        run.setFailureCode(null);
        run.setCompletedAt(LocalDateTime.now());
    }

    @Transactional
    public void completeFailure(Long runId, String failureCode) {
        KeywordRecommendationRun run = findRun(runId);
        run.setStatus(KeywordRecommendationRunStatus.FAILURE);
        run.setActiveSlot(null);
        run.setFailureCode(failureCode);
        run.setCompletedAt(LocalDateTime.now());
    }

    @Transactional
    public KeywordRecommendationRunResponse getLatest(Long targetGroupId) {
        return keywordRecommendationRunRepository.findFirstByTargetGroupIdOrderByRequestedAtDesc(targetGroupId)
                .map(run -> {
                    recoverIfStale(run);
                    return KeywordRecommendationRunResponse.from(run);
                })
                .orElse(null);
    }

    private KeywordRecommendationRun findRun(Long runId) {
        return keywordRecommendationRunRepository.findById(runId)
                .orElseThrow(() -> new IllegalArgumentException("Recommendation run not found."));
    }

    private boolean recoverIfStale(KeywordRecommendationRun activeRun) {
        if (activeRun.getActiveSlot() == null) {
            return false;
        }
        LocalDateTime staleBefore = LocalDateTime.now().minus(STALE_RUN_MINUTES, ChronoUnit.MINUTES);
        LocalDateTime lastActivityAt = activeRun.getStartedAt() != null
                ? activeRun.getStartedAt()
                : activeRun.getRequestedAt();
        if (lastActivityAt != null && lastActivityAt.isBefore(staleBefore)) {
            activeRun.setStatus(KeywordRecommendationRunStatus.FAILURE);
            activeRun.setActiveSlot(null);
            activeRun.setFailureCode("STALE_RUN_RECOVERED");
            activeRun.setCompletedAt(LocalDateTime.now());
            keywordRecommendationRunRepository.saveAndFlush(activeRun);
            return true;
        }
        return false;
    }

    public record RecommendationRunContext(Long runId, Long targetGroupId, String targetKeyword) {
    }
}
