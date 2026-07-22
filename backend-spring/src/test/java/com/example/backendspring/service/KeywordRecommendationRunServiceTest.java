package com.example.backendspring.service;

import com.example.backendspring.dto.KeywordRecommendationRunResponse;
import com.example.backendspring.entity.KeywordGroup;
import com.example.backendspring.entity.KeywordRecommendationRun;
import com.example.backendspring.entity.KeywordRecommendationRunStatus;
import com.example.backendspring.repository.KeywordGroupRepository;
import com.example.backendspring.repository.KeywordRecommendationRunRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class KeywordRecommendationRunServiceTest {

    @Mock
    private KeywordRecommendationRunRepository runRepository;

    @Mock
    private KeywordGroupRepository groupRepository;

    @Test
    void createsPendingRunWithSingleActiveSlot() {
        KeywordGroup group = activeGroup();
        when(runRepository.findFirstByActiveSlotOrderByRequestedAtDesc(1)).thenReturn(Optional.empty());
        when(groupRepository.findById(1L)).thenReturn(Optional.of(group));
        when(runRepository.saveAndFlush(any())).thenAnswer(invocation -> {
            KeywordRecommendationRun run = invocation.getArgument(0);
            run.setId(10L);
            return run;
        });

        KeywordRecommendationRunResponse response = service().request(1L, "admin@example.com");

        assertThat(response.id()).isEqualTo(10L);
        assertThat(response.status()).isEqualTo(KeywordRecommendationRunStatus.PENDING);
        ArgumentCaptor<KeywordRecommendationRun> captor = ArgumentCaptor.forClass(KeywordRecommendationRun.class);
        verify(runRepository).saveAndFlush(captor.capture());
        assertThat(captor.getValue().getActiveSlot()).isEqualTo(1);
    }

    @Test
    void rejectsRequestWhenAnotherRunIsActive() {
        when(runRepository.findFirstByActiveSlotOrderByRequestedAtDesc(1))
                .thenReturn(Optional.of(KeywordRecommendationRun.builder().build()));

        assertThatThrownBy(() -> service().request(1L, "admin@example.com"))
                .isInstanceOf(ResponseStatusException.class)
                .extracting(error -> ((ResponseStatusException) error).getStatusCode().value())
                .isEqualTo(409);
    }

    @Test
    void recordsSuccessCountsAndReleasesActiveSlot() {
        KeywordRecommendationRun run = KeywordRecommendationRun.builder()
                .status(KeywordRecommendationRunStatus.RUNNING)
                .activeSlot(1)
                .build();
        when(runRepository.findById(10L)).thenReturn(Optional.of(run));

        service().completeSuccess(10L, 200, 3, 2);

        assertThat(run.getStatus()).isEqualTo(KeywordRecommendationRunStatus.SUCCESS);
        assertThat(run.getActiveSlot()).isNull();
        assertThat(run.getCandidateCount()).isEqualTo(200);
        assertThat(run.getSavedSuggestionCount()).isEqualTo(2);
        assertThat(run.getCompletedAt()).isNotNull();
    }

    @Test
    void recoversStaleRunBeforeCreatingNewRequest() {
        KeywordRecommendationRun staleRun = KeywordRecommendationRun.builder()
                .status(KeywordRecommendationRunStatus.RUNNING)
                .activeSlot(1)
                .startedAt(LocalDateTime.now().minusMinutes(11))
                .build();
        KeywordGroup group = activeGroup();
        when(runRepository.findFirstByActiveSlotOrderByRequestedAtDesc(1)).thenReturn(Optional.of(staleRun));
        when(groupRepository.findById(1L)).thenReturn(Optional.of(group));
        when(runRepository.saveAndFlush(any())).thenAnswer(invocation -> {
            KeywordRecommendationRun run = invocation.getArgument(0);
            if (run.getId() == null) {
                run.setId(11L);
            }
            return run;
        });

        KeywordRecommendationRunResponse response = service().request(1L, "admin@example.com");

        assertThat(staleRun.getStatus()).isEqualTo(KeywordRecommendationRunStatus.FAILURE);
        assertThat(staleRun.getActiveSlot()).isNull();
        assertThat(staleRun.getFailureCode()).isEqualTo("STALE_RUN_RECOVERED");
        assertThat(response.status()).isEqualTo(KeywordRecommendationRunStatus.PENDING);
    }

    @Test
    void latestLookupRecoversStaleRunSoPollingCanStop() {
        KeywordRecommendationRun staleRun = KeywordRecommendationRun.builder()
                .targetGroup(activeGroup())
                .status(KeywordRecommendationRunStatus.PENDING)
                .activeSlot(1)
                .requestedAt(LocalDateTime.now().minusMinutes(11))
                .build();
        when(runRepository.findFirstByTargetGroupIdOrderByRequestedAtDesc(1L)).thenReturn(Optional.of(staleRun));
        when(runRepository.saveAndFlush(staleRun)).thenReturn(staleRun);

        KeywordRecommendationRunResponse response = service().getLatest(1L);

        assertThat(response.status()).isEqualTo(KeywordRecommendationRunStatus.FAILURE);
        assertThat(response.failureCode()).isEqualTo("STALE_RUN_RECOVERED");
        assertThat(staleRun.getActiveSlot()).isNull();
    }

    private KeywordRecommendationRunService service() {
        return new KeywordRecommendationRunService(runRepository, groupRepository);
    }

    private KeywordGroup activeGroup() {
        return KeywordGroup.builder()
                .id(1L)
                .canonicalKeyword("AI")
                .active(true)
                .build();
    }
}
