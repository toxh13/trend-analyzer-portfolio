package com.example.backendspring.service;

import com.example.backendspring.dto.CrawlBatchRunCompleteRequest;
import com.example.backendspring.dto.CrawlBatchRunResponse;
import com.example.backendspring.dto.CrawlBatchRunStartRequest;
import com.example.backendspring.dto.CrawlChannelRunRequest;
import com.example.backendspring.dto.CrawlChannelRunResponse;
import com.example.backendspring.entity.CrawlBatchRun;
import com.example.backendspring.entity.CrawlChannelRun;
import com.example.backendspring.entity.CrawlRunOutcome;
import com.example.backendspring.repository.CrawlBatchRunRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Pageable;
import org.springframework.web.server.ResponseStatusException;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CrawlBatchRunServiceTest {

    private static final String RUN_ID = "11111111-1111-4111-8111-111111111111";
    private static final OffsetDateTime STARTED_AT = OffsetDateTime.parse("2026-07-20T00:00:00Z");
    private static final OffsetDateTime COMPLETED_AT = OffsetDateTime.parse("2026-07-20T00:01:00Z");

    @Mock
    private CrawlBatchRunRepository repository;

    @Test
    void createsRunningHistoryAndReusesSameStartRequest() {
        CrawlBatchRunService service = new CrawlBatchRunService(repository);
        CrawlBatchRunStartRequest request = new CrawlBatchRunStartRequest(RUN_ID, STARTED_AT);
        when(repository.saveAndFlush(any())).thenAnswer(invocation -> invocation.getArgument(0));

        CrawlBatchRunResponse created = service.start(request);

        assertThat(created.outcome()).isEqualTo(CrawlRunOutcome.RUNNING);
        assertThat(created.completedAt()).isNull();

        CrawlBatchRun running = runningEntity();
        when(repository.findByRunId(RUN_ID)).thenReturn(Optional.of(running));
        assertThat(service.start(request).runId()).isEqualTo(RUN_ID);
    }

    @Test
    void completesExistingRunningHistory() {
        CrawlBatchRun running = runningEntity();
        when(repository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(running));
        when(repository.saveAndFlush(any())).thenAnswer(invocation -> invocation.getArgument(0));

        CrawlBatchRunResponse response = new CrawlBatchRunService(repository).complete(successRequest());

        assertThat(response.outcome()).isEqualTo(CrawlRunOutcome.SUCCESS);
        assertThat(response.completedAt()).isEqualTo(COMPLETED_AT);
        assertThat(response.channels()).hasSize(3);
    }

    @Test
    void savesAllFourOutcomesUsingServerCalculatedRules() {
        CrawlBatchRunService service = new CrawlBatchRunService(repository);
        when(repository.saveAndFlush(any())).thenAnswer(invocation -> invocation.getArgument(0));

        assertThat(service.complete(successRequest()).outcome()).isEqualTo(CrawlRunOutcome.SUCCESS);
        assertThat(service.complete(emptyRequest()).outcome()).isEqualTo(CrawlRunOutcome.EMPTY);
        assertThat(service.complete(partialRequest()).outcome()).isEqualTo(CrawlRunOutcome.PARTIAL_FAILURE);
        assertThat(service.complete(failureRequest()).outcome()).isEqualTo(CrawlRunOutcome.FAILURE);
    }

    @Test
    void sameRunIdAndSamePayloadReturnsExistingSnapshot() {
        CrawlBatchRunCompleteRequest request = successRequest();
        CrawlBatchRun existing = entityFrom(request);
        when(repository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(existing));

        CrawlBatchRunResponse response = new CrawlBatchRunService(repository).complete(request);

        assertThat(response.runId()).isEqualTo(RUN_ID);
        verify(repository, never()).saveAndFlush(any());
    }

    @Test
    void detailReconciliationIncludesChannelRows() {
        CrawlBatchRun run = entityFrom(successRequest());
        assertThat(CrawlBatchRunResponse.from(run).reconciliationOk()).isTrue();

        run.getChannels().remove(0);

        assertThat(CrawlBatchRunResponse.from(run).reconciliationOk()).isFalse();
        assertThat(CrawlBatchRunResponse.summaryFrom(run).reconciliationOk()).isTrue();
    }

    @Test
    void sameInstantWithDifferentOffsetReturnsExistingSnapshot() {
        CrawlBatchRunCompleteRequest request = successRequest();
        CrawlBatchRun existing = entityFrom(request);
        when(repository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(existing));
        CrawlBatchRunCompleteRequest differentOffset = new CrawlBatchRunCompleteRequest(
                request.runId(), request.startedAt().withOffsetSameInstant(ZoneOffset.ofHours(9)),
                request.completedAt().withOffsetSameInstant(ZoneOffset.ofHours(9)), request.outcome(),
                request.crawlerOutputCount(), request.validationRejectedCount(), request.duplicateUrlCount(),
                request.eligibleCount(), request.selectedCount(), request.droppedByLimitCount(),
                request.preprocessingFailedCount(), request.backendAcknowledgedCount(), request.httpFailedCount(),
                request.transportFailedCount(), request.durationMs(), request.channels()
        );

        CrawlBatchRunResponse response = new CrawlBatchRunService(repository).complete(differentOffset);

        assertThat(response.startedAt()).isEqualTo(STARTED_AT);
        verify(repository, never()).saveAndFlush(any());
    }

    @Test
    void truncatesApiNanosecondsToOracleTimestampMicrosecondsForReplay() {
        OffsetDateTime preciseStart = OffsetDateTime.parse("2026-07-20T00:00:00.123456789Z");
        CrawlBatchRunStartRequest request = new CrawlBatchRunStartRequest(RUN_ID, preciseStart);
        CrawlBatchRun existing = CrawlBatchRun.builder()
                .runId(RUN_ID)
                .startedAt(OffsetDateTime.parse("2026-07-20T00:00:00.123456Z").toLocalDateTime())
                .outcome(CrawlRunOutcome.RUNNING)
                .createdAt(STARTED_AT.toLocalDateTime())
                .build();
        when(repository.findByRunId(RUN_ID)).thenReturn(Optional.of(existing));

        assertThat(new CrawlBatchRunService(repository).start(request).runId()).isEqualTo(RUN_ID);
        verify(repository, never()).saveAndFlush(any());
    }

    @Test
    void sameRunIdAndDifferentPayloadReturnsConflict() {
        CrawlBatchRunCompleteRequest request = successRequest();
        CrawlBatchRun existing = entityFrom(request);
        when(repository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(existing));
        CrawlBatchRunCompleteRequest conflicting = copyWithDuration(request, 61_000);

        assertThatThrownBy(() -> new CrawlBatchRunService(repository).complete(conflicting))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("409 CONFLICT");
    }

    @Test
    void uniqueRaceReturnsTheConcurrentlySavedIdenticalSnapshot() {
        CrawlBatchRunCompleteRequest request = successRequest();
        CrawlBatchRun existing = entityFrom(request);
        when(repository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.empty());
        when(repository.findByRunId(RUN_ID)).thenReturn(Optional.of(existing));
        when(repository.saveAndFlush(any())).thenThrow(new DataIntegrityViolationException("unique"));

        CrawlBatchRunResponse response = new CrawlBatchRunService(repository).complete(request);

        assertThat(response.runId()).isEqualTo(RUN_ID);
    }

    @Test
    void rejectsBrokenReconciliation() {
        CrawlBatchRunCompleteRequest request = successRequest();
        CrawlBatchRunCompleteRequest broken = new CrawlBatchRunCompleteRequest(
                request.runId(), request.startedAt(), request.completedAt(), request.outcome(),
                4L, request.validationRejectedCount(), request.duplicateUrlCount(), request.eligibleCount(),
                request.selectedCount(), request.droppedByLimitCount(), request.preprocessingFailedCount(),
                request.backendAcknowledgedCount(), request.httpFailedCount(), request.transportFailedCount(),
                request.durationMs(), request.channels()
        );

        assertThatThrownBy(() -> new CrawlBatchRunService(repository).complete(broken))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("400 BAD_REQUEST");
    }

    @Test
    void acceptsChannelCountsAfterCommonValidationRejections() {
        CrawlBatchRunCompleteRequest request = request(
                CrawlRunOutcome.PARTIAL_FAILURE, 4, 3, 0, 1, successChannels()
        );
        when(repository.saveAndFlush(any())).thenAnswer(invocation -> invocation.getArgument(0));

        CrawlBatchRunResponse response = new CrawlBatchRunService(repository).complete(request);

        assertThat(response.crawlerOutputCount()).isEqualTo(4);
        assertThat(response.validationRejectedCount()).isEqualTo(1);
        assertThat(response.channels()).extracting(CrawlChannelRunResponse::validatedArticleCount)
                .containsExactly(1L, 1L, 1L);
    }

    @Test
    void classifiesAllValidationRejectedAsPartialFailure() {
        CrawlBatchRunCompleteRequest request = request(
                CrawlRunOutcome.PARTIAL_FAILURE, 3, 0, 0, 3, successChannels()
        );
        List<CrawlChannelRunRequest> emptyAfterValidation = List.of(
                channel("naver", CrawlRunOutcome.SUCCESS, 0, 0, 1, 0, 0, 0),
                channel("daum", CrawlRunOutcome.SUCCESS, 0, 0, 1, 0, 0, 0),
                channel("rss", CrawlRunOutcome.SUCCESS, 0, 0, 1, 0, 0, 0)
        );
        request = new CrawlBatchRunCompleteRequest(
                request.runId(), request.startedAt(), request.completedAt(), request.outcome(),
                3L, 3L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L,
                request.durationMs(), emptyAfterValidation
        );
        when(repository.saveAndFlush(any())).thenAnswer(invocation -> invocation.getArgument(0));

        assertThat(new CrawlBatchRunService(repository).complete(request).outcome())
                .isEqualTo(CrawlRunOutcome.PARTIAL_FAILURE);
    }

    @Test
    void rejectsOutcomeThatDoesNotMatchPythonRule() {
        CrawlBatchRunCompleteRequest request = partialRequest();
        CrawlBatchRunCompleteRequest broken = new CrawlBatchRunCompleteRequest(
                request.runId(), request.startedAt(), request.completedAt(), CrawlRunOutcome.SUCCESS,
                request.crawlerOutputCount(), request.validationRejectedCount(), request.duplicateUrlCount(),
                request.eligibleCount(), request.selectedCount(), request.droppedByLimitCount(),
                request.preprocessingFailedCount(), request.backendAcknowledgedCount(), request.httpFailedCount(),
                request.transportFailedCount(), request.durationMs(), request.channels()
        );

        assertThatThrownBy(() -> new CrawlBatchRunService(repository).complete(broken))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("outcome");
    }

    @Test
    void rejectsCompletionBeforeStart() {
        CrawlBatchRunCompleteRequest request = successRequest();
        CrawlBatchRunCompleteRequest broken = new CrawlBatchRunCompleteRequest(
                request.runId(), request.completedAt(), request.startedAt(), request.outcome(),
                request.crawlerOutputCount(), request.validationRejectedCount(), request.duplicateUrlCount(),
                request.eligibleCount(), request.selectedCount(), request.droppedByLimitCount(),
                request.preprocessingFailedCount(), request.backendAcknowledgedCount(), request.httpFailedCount(),
                request.transportFailedCount(), request.durationMs(), request.channels()
        );

        assertThatThrownBy(() -> new CrawlBatchRunService(repository).complete(broken))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("completedAt");
    }

    @Test
    void requestsLatestRunsWithValidatedLimit() {
        CrawlBatchRun first = entityFrom(successRequest());
        CrawlBatchRun second = entityFrom(copyWithRunId(successRequest(), "22222222-2222-4222-8222-222222222222"));
        when(repository.findByOrderByStartedAtDesc(any())).thenReturn(List.of(first, second));
        CrawlBatchRunService service = new CrawlBatchRunService(repository);

        List<CrawlBatchRunResponse> result = service.getRecent(20);

        assertThat(result).extracting(CrawlBatchRunResponse::runId)
                .containsExactly(first.getRunId(), second.getRunId());
        ArgumentCaptor<Pageable> pageable = ArgumentCaptor.forClass(Pageable.class);
        verify(repository).findByOrderByStartedAtDesc(pageable.capture());
        assertThat(pageable.getValue().getPageSize()).isEqualTo(20);
        assertThatThrownBy(() -> service.getRecent(0)).isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> service.getRecent(51)).isInstanceOf(ResponseStatusException.class);
    }

    @Test
    void missingRunReturnsNotFound() {
        when(repository.findByRunId("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> new CrawlBatchRunService(repository).getByRunId("missing"))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("404 NOT_FOUND");
    }

    private CrawlBatchRunCompleteRequest successRequest() {
        return request(CrawlRunOutcome.SUCCESS, 3, 3, 0, 0, successChannels());
    }

    private CrawlBatchRunCompleteRequest emptyRequest() {
        return request(CrawlRunOutcome.EMPTY, 0, 0, 0, 0, List.of(
                channel("naver", CrawlRunOutcome.EMPTY, 0, 0, 0, 0, 1, 0),
                channel("daum", CrawlRunOutcome.EMPTY, 0, 0, 0, 0, 1, 0),
                channel("rss", CrawlRunOutcome.EMPTY, 0, 0, 0, 0, 1, 0)
        ));
    }

    private CrawlBatchRunCompleteRequest partialRequest() {
        return request(CrawlRunOutcome.PARTIAL_FAILURE, 3, 3, 1, 0, List.of(
                channel("naver", CrawlRunOutcome.PARTIAL_FAILURE, 1, 1, 0, 1, 0, 0),
                channel("daum", CrawlRunOutcome.SUCCESS, 1, 0, 1, 0, 0, 0),
                channel("rss", CrawlRunOutcome.SUCCESS, 1, 0, 1, 0, 0, 0)
        ));
    }

    private CrawlBatchRunCompleteRequest failureRequest() {
        return request(CrawlRunOutcome.FAILURE, 0, 0, 0, 0, List.of(
                channel("naver", CrawlRunOutcome.FAILURE, 0, 0, 0, 0, 0, 1),
                channel("daum", CrawlRunOutcome.EMPTY, 0, 0, 0, 0, 1, 0),
                channel("rss", CrawlRunOutcome.EMPTY, 0, 0, 0, 0, 1, 0)
        ));
    }

    private CrawlBatchRunCompleteRequest request(
            CrawlRunOutcome outcome, long output, long selected, long httpFailed, long validationRejected,
            List<CrawlChannelRunRequest> channels
    ) {
        return new CrawlBatchRunCompleteRequest(
                RUN_ID, STARTED_AT, COMPLETED_AT, outcome,
                output, validationRejected, 0L, selected, selected, 0L,
                0L, selected - httpFailed, httpFailed, 0L, 60_000L, channels
        );
    }

    private List<CrawlChannelRunRequest> successChannels() {
        return List.of(
                channel("naver", CrawlRunOutcome.SUCCESS, 1, 0, 1, 0, 0, 0),
                channel("daum", CrawlRunOutcome.SUCCESS, 1, 0, 1, 0, 0, 0),
                channel("rss", CrawlRunOutcome.SUCCESS, 1, 0, 1, 0, 0, 0)
        );
    }

    private CrawlChannelRunRequest channel(
            String name, CrawlRunOutcome outcome, long validatedArticleCount, long sourceInvalid,
            long success, long partial, long empty, long failed
    ) {
        return new CrawlChannelRunRequest(name, outcome, validatedArticleCount, sourceInvalid, success, partial, empty, failed);
    }

    private CrawlBatchRun entityFrom(CrawlBatchRunCompleteRequest request) {
        long sourceInvalid = request.channels().stream().mapToLong(CrawlChannelRunRequest::sourceInvalidCount).sum();
        CrawlBatchRun run = CrawlBatchRun.builder()
                .runId(request.runId())
                .startedAt(request.startedAt().withOffsetSameInstant(ZoneOffset.UTC).toLocalDateTime())
                .completedAt(request.completedAt().withOffsetSameInstant(ZoneOffset.UTC).toLocalDateTime())
                .outcome(request.outcome()).crawlerOutputCount(request.crawlerOutputCount())
                .sourceInvalidCount(sourceInvalid).validationRejectedCount(request.validationRejectedCount())
                .duplicateUrlCount(request.duplicateUrlCount()).eligibleCount(request.eligibleCount())
                .selectedCount(request.selectedCount()).droppedByLimitCount(request.droppedByLimitCount())
                .preprocessingFailedCount(request.preprocessingFailedCount())
                .backendAcknowledgedCount(request.backendAcknowledgedCount()).httpFailedCount(request.httpFailedCount())
                .transportFailedCount(request.transportFailedCount())
                .successfulChannelCount(countChannels(request, CrawlRunOutcome.SUCCESS))
                .partialChannelCount(countChannels(request, CrawlRunOutcome.PARTIAL_FAILURE))
                .emptyChannelCount(countChannels(request, CrawlRunOutcome.EMPTY))
                .failedChannelCount(countChannels(request, CrawlRunOutcome.FAILURE))
                .successfulUnitCount(request.channels().stream().mapToLong(CrawlChannelRunRequest::successfulUnits).sum())
                .partialUnitCount(request.channels().stream().mapToLong(CrawlChannelRunRequest::partialUnits).sum())
                .emptyUnitCount(request.channels().stream().mapToLong(CrawlChannelRunRequest::emptyUnits).sum())
                .failedUnitCount(request.channels().stream().mapToLong(CrawlChannelRunRequest::failedUnits).sum())
                .durationMs(request.durationMs())
                .createdAt(COMPLETED_AT.toLocalDateTime()).build();
        request.channels().forEach(channel -> run.addChannel(CrawlChannelRun.builder()
                .channel(channel.channel()).outcome(channel.outcome()).validatedArticleCount(channel.validatedArticleCount())
                .sourceInvalidCount(channel.sourceInvalidCount()).successfulUnits(channel.successfulUnits())
                .partialUnits(channel.partialUnits()).emptyUnits(channel.emptyUnits()).failedUnits(channel.failedUnits())
                .build()));
        return run;
    }

    private long countChannels(CrawlBatchRunCompleteRequest request, CrawlRunOutcome outcome) {
        return request.channels().stream().filter(channel -> channel.outcome() == outcome).count();
    }

    private CrawlBatchRun runningEntity() {
        return CrawlBatchRun.builder()
                .runId(RUN_ID)
                .startedAt(STARTED_AT.toLocalDateTime())
                .outcome(CrawlRunOutcome.RUNNING)
                .createdAt(STARTED_AT.toLocalDateTime())
                .build();
    }

    private CrawlBatchRunCompleteRequest copyWithDuration(CrawlBatchRunCompleteRequest request, long duration) {
        return new CrawlBatchRunCompleteRequest(
                request.runId(), request.startedAt(), request.completedAt(), request.outcome(),
                request.crawlerOutputCount(), request.validationRejectedCount(), request.duplicateUrlCount(),
                request.eligibleCount(), request.selectedCount(), request.droppedByLimitCount(),
                request.preprocessingFailedCount(), request.backendAcknowledgedCount(), request.httpFailedCount(),
                request.transportFailedCount(), duration, request.channels()
        );
    }

    private CrawlBatchRunCompleteRequest copyWithRunId(CrawlBatchRunCompleteRequest request, String runId) {
        return new CrawlBatchRunCompleteRequest(
                runId, request.startedAt(), request.completedAt(), request.outcome(),
                request.crawlerOutputCount(), request.validationRejectedCount(), request.duplicateUrlCount(),
                request.eligibleCount(), request.selectedCount(), request.droppedByLimitCount(),
                request.preprocessingFailedCount(), request.backendAcknowledgedCount(), request.httpFailedCount(),
                request.transportFailedCount(), request.durationMs(), request.channels()
        );
    }
}
