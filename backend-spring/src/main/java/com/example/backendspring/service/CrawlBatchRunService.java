package com.example.backendspring.service;

import com.example.backendspring.dto.CrawlBatchRunCompleteRequest;
import com.example.backendspring.dto.CrawlBatchRunResponse;
import com.example.backendspring.dto.CrawlBatchRunStartRequest;
import com.example.backendspring.dto.CrawlChannelRunRequest;
import com.example.backendspring.entity.CrawlBatchRun;
import com.example.backendspring.entity.CrawlChannelRun;
import com.example.backendspring.entity.CrawlRunOutcome;
import com.example.backendspring.repository.CrawlBatchRunRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class CrawlBatchRunService {

    private static final Set<String> REQUIRED_CHANNELS = Set.of("naver", "daum", "rss");

    private final CrawlBatchRunRepository crawlBatchRunRepository;

    public CrawlBatchRunResponse start(CrawlBatchRunStartRequest request) {
        validateRunId(request.runId());
        LocalDateTime startedAt = toUtcLocalDateTime(request.startedAt());
        CrawlBatchRun existing = crawlBatchRunRepository.findByRunId(request.runId()).orElse(null);
        if (existing != null) {
            return idempotentStartResponse(existing, startedAt);
        }

        CrawlBatchRun run = CrawlBatchRun.builder()
                .runId(request.runId())
                .startedAt(startedAt)
                .outcome(CrawlRunOutcome.RUNNING)
                .createdAt(LocalDateTime.now(ZoneOffset.UTC))
                .build();
        try {
            return CrawlBatchRunResponse.from(crawlBatchRunRepository.saveAndFlush(run));
        } catch (DataIntegrityViolationException error) {
            CrawlBatchRun concurrentlySaved = crawlBatchRunRepository.findByRunId(request.runId()).orElse(null);
            if (concurrentlySaved == null) {
                throw error;
            }
            return idempotentStartResponse(concurrentlySaved, startedAt);
        }
    }

    @Transactional
    public CrawlBatchRunResponse complete(CrawlBatchRunCompleteRequest request) {
        ValidatedRun validated = validate(request);
        CrawlBatchRun existing = crawlBatchRunRepository.findByRunIdForUpdate(request.runId()).orElse(null);
        if (existing != null && existing.getOutcome() != CrawlRunOutcome.RUNNING) {
            return idempotentResponse(existing, request, validated);
        }

        CrawlBatchRun run = toEntity(request, validated);
        if (existing != null) {
            if (!existing.getStartedAt().equals(run.getStartedAt())) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "같은 runId의 시작 시각이 기존 이력과 다릅니다.");
            }
            existing.completeFrom(run);
            return CrawlBatchRunResponse.from(crawlBatchRunRepository.saveAndFlush(existing));
        }
        try {
            return CrawlBatchRunResponse.from(crawlBatchRunRepository.saveAndFlush(run));
        } catch (DataIntegrityViolationException error) {
            CrawlBatchRun concurrentlySaved = crawlBatchRunRepository.findByRunId(request.runId()).orElse(null);
            if (concurrentlySaved == null) {
                throw error;
            }
            return idempotentResponse(concurrentlySaved, request, validated);
        }
    }

    @Transactional(readOnly = true)
    public List<CrawlBatchRunResponse> getRecent(int limit) {
        if (limit < 1 || limit > 50) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit는 1~50 사이여야 합니다.");
        }
        return crawlBatchRunRepository.findByOrderByStartedAtDesc(PageRequest.of(0, limit)).stream()
                .map(CrawlBatchRunResponse::summaryFrom)
                .toList();
    }

    @Transactional(readOnly = true)
    public CrawlBatchRunResponse getByRunId(String runId) {
        return crawlBatchRunRepository.findByRunId(runId)
                .map(CrawlBatchRunResponse::from)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "수집 실행 이력을 찾을 수 없습니다."));
    }

    private ValidatedRun validate(CrawlBatchRunCompleteRequest request) {
        if (request.completedAt().isBefore(request.startedAt())) {
            badRequest("completedAt은 startedAt보다 빠를 수 없습니다.");
        }
        validateRunId(request.runId());

        Set<String> channelNames = new HashSet<>();
        long sourceInvalid = 0;
        long validatedArticleCount = 0;
        long successfulChannels = 0;
        long partialChannels = 0;
        long emptyChannels = 0;
        long failedChannels = 0;
        long successfulUnits = 0;
        long partialUnits = 0;
        long emptyUnits = 0;
        long failedUnits = 0;

        for (CrawlChannelRunRequest channel : request.channels()) {
            String normalizedName = channel.channel().trim().toLowerCase(Locale.ROOT);
            if (!REQUIRED_CHANNELS.contains(normalizedName) || !channelNames.add(normalizedName)) {
                badRequest("channels에는 naver, daum, rss가 각각 한 번씩 필요합니다.");
            }
            CrawlRunOutcome expectedChannelOutcome = calculateChannelOutcome(channel);
            if (channel.outcome() != expectedChannelOutcome) {
                badRequest(normalizedName + " 채널 outcome이 unit 상태와 일치하지 않습니다.");
            }

            sourceInvalid = add(sourceInvalid, channel.sourceInvalidCount());
            validatedArticleCount = add(validatedArticleCount, channel.validatedArticleCount());
            successfulUnits = add(successfulUnits, channel.successfulUnits());
            partialUnits = add(partialUnits, channel.partialUnits());
            emptyUnits = add(emptyUnits, channel.emptyUnits());
            failedUnits = add(failedUnits, channel.failedUnits());
            switch (channel.outcome()) {
                case SUCCESS -> successfulChannels++;
                case PARTIAL_FAILURE -> partialChannels++;
                case EMPTY -> emptyChannels++;
                case FAILURE -> failedChannels++;
            }
        }
        if (!channelNames.equals(REQUIRED_CHANNELS)) {
            badRequest("channels에는 naver, daum, rss가 각각 한 번씩 필요합니다.");
        }
        long reconciledOutput = add(request.validationRejectedCount(), request.duplicateUrlCount(), request.eligibleCount());
        long reconciledEligible = add(request.selectedCount(), request.droppedByLimitCount());
        long reconciledSelected = add(
                request.preprocessingFailedCount(), request.backendAcknowledgedCount(),
                request.httpFailedCount(), request.transportFailedCount()
        );
        if (request.crawlerOutputCount() != reconciledOutput
                || request.eligibleCount() != reconciledEligible
                || request.selectedCount() != reconciledSelected) {
            badRequest("수집 단계별 수량 대사가 일치하지 않습니다.");
        }
        if (validatedArticleCount != add(request.duplicateUrlCount(), request.eligibleCount())) {
            badRequest("채널 validatedArticleCount 합계가 공통 검증 통과 수와 일치하지 않습니다.");
        }

        CrawlRunOutcome expectedOutcome = calculateBatchOutcome(request, partialUnits, failedUnits);
        if (request.outcome() != expectedOutcome) {
            badRequest("outcome이 서버에서 계산한 배치 결과와 일치하지 않습니다.");
        }

        return new ValidatedRun(
                sourceInvalid, successfulChannels, partialChannels, emptyChannels, failedChannels,
                successfulUnits, partialUnits, emptyUnits, failedUnits
        );
    }

    private CrawlRunOutcome calculateChannelOutcome(CrawlChannelRunRequest channel) {
        long totalUnits = add(channel.successfulUnits(), channel.partialUnits(), channel.emptyUnits(), channel.failedUnits());
        if (totalUnits == 0 || channel.emptyUnits() == totalUnits) {
            return CrawlRunOutcome.EMPTY;
        }
        if (channel.successfulUnits() == 0 && channel.partialUnits() == 0 && channel.failedUnits() > 0) {
            return CrawlRunOutcome.FAILURE;
        }
        if (channel.partialUnits() > 0 || channel.emptyUnits() > 0 || channel.failedUnits() > 0) {
            return CrawlRunOutcome.PARTIAL_FAILURE;
        }
        return CrawlRunOutcome.SUCCESS;
    }

    private CrawlRunOutcome calculateBatchOutcome(
            CrawlBatchRunCompleteRequest request,
            long partialUnits,
            long failedUnits
    ) {
        if (request.selectedCount() == 0) {
            if (failedUnits > 0) {
                return CrawlRunOutcome.FAILURE;
            }
            if (partialUnits > 0 || request.validationRejectedCount() > 0) {
                return CrawlRunOutcome.PARTIAL_FAILURE;
            }
            return CrawlRunOutcome.EMPTY;
        }
        if (request.backendAcknowledgedCount() == 0) {
            return CrawlRunOutcome.FAILURE;
        }
        long deliveryFailures = add(
                request.preprocessingFailedCount(), request.httpFailedCount(), request.transportFailedCount()
        );
        if (failedUnits > 0 || partialUnits > 0 || request.validationRejectedCount() > 0 || deliveryFailures > 0) {
            return CrawlRunOutcome.PARTIAL_FAILURE;
        }
        return CrawlRunOutcome.SUCCESS;
    }

    private CrawlBatchRun toEntity(CrawlBatchRunCompleteRequest request, ValidatedRun validated) {
        CrawlBatchRun run = CrawlBatchRun.builder()
                .runId(request.runId())
                .startedAt(toUtcLocalDateTime(request.startedAt()))
                .completedAt(toUtcLocalDateTime(request.completedAt()))
                .outcome(request.outcome())
                .crawlerOutputCount(request.crawlerOutputCount())
                .sourceInvalidCount(validated.sourceInvalidCount())
                .validationRejectedCount(request.validationRejectedCount())
                .duplicateUrlCount(request.duplicateUrlCount())
                .eligibleCount(request.eligibleCount())
                .selectedCount(request.selectedCount())
                .droppedByLimitCount(request.droppedByLimitCount())
                .preprocessingFailedCount(request.preprocessingFailedCount())
                .backendAcknowledgedCount(request.backendAcknowledgedCount())
                .httpFailedCount(request.httpFailedCount())
                .transportFailedCount(request.transportFailedCount())
                .successfulChannelCount(validated.successfulChannelCount())
                .partialChannelCount(validated.partialChannelCount())
                .emptyChannelCount(validated.emptyChannelCount())
                .failedChannelCount(validated.failedChannelCount())
                .successfulUnitCount(validated.successfulUnitCount())
                .partialUnitCount(validated.partialUnitCount())
                .emptyUnitCount(validated.emptyUnitCount())
                .failedUnitCount(validated.failedUnitCount())
                .durationMs(request.durationMs())
                .createdAt(LocalDateTime.now(ZoneOffset.UTC))
                .build();
        request.channels().stream()
                .sorted((left, right) -> left.channel().compareToIgnoreCase(right.channel()))
                .map(this::toChannelEntity)
                .forEach(run::addChannel);
        return run;
    }

    private CrawlChannelRun toChannelEntity(CrawlChannelRunRequest channel) {
        return CrawlChannelRun.builder()
                .channel(channel.channel().trim().toLowerCase(Locale.ROOT))
                .outcome(channel.outcome())
                .validatedArticleCount(channel.validatedArticleCount())
                .sourceInvalidCount(channel.sourceInvalidCount())
                .successfulUnits(channel.successfulUnits())
                .partialUnits(channel.partialUnits())
                .emptyUnits(channel.emptyUnits())
                .failedUnits(channel.failedUnits())
                .build();
    }

    private CrawlBatchRunResponse idempotentResponse(
            CrawlBatchRun existing,
            CrawlBatchRunCompleteRequest request,
            ValidatedRun validated
    ) {
        if (!samePayload(existing, request, validated)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "같은 runId에 다른 완료 결과가 이미 저장되어 있습니다.");
        }
        return CrawlBatchRunResponse.from(existing);
    }

    private CrawlBatchRunResponse idempotentStartResponse(CrawlBatchRun existing, LocalDateTime startedAt) {
        if (!existing.getStartedAt().equals(startedAt)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "같은 runId의 시작 시각이 기존 이력과 다릅니다.");
        }
        return CrawlBatchRunResponse.from(existing);
    }

    private boolean samePayload(CrawlBatchRun existing, CrawlBatchRunCompleteRequest request, ValidatedRun validated) {
        if (!existing.getStartedAt().equals(toUtcLocalDateTime(request.startedAt()))
                || !existing.getCompletedAt().equals(toUtcLocalDateTime(request.completedAt()))
                || existing.getOutcome() != request.outcome()
                || existing.getCrawlerOutputCount() != request.crawlerOutputCount()
                || existing.getSourceInvalidCount() != validated.sourceInvalidCount()
                || existing.getValidationRejectedCount() != request.validationRejectedCount()
                || existing.getDuplicateUrlCount() != request.duplicateUrlCount()
                || existing.getEligibleCount() != request.eligibleCount()
                || existing.getSelectedCount() != request.selectedCount()
                || existing.getDroppedByLimitCount() != request.droppedByLimitCount()
                || existing.getPreprocessingFailedCount() != request.preprocessingFailedCount()
                || existing.getBackendAcknowledgedCount() != request.backendAcknowledgedCount()
                || existing.getHttpFailedCount() != request.httpFailedCount()
                || existing.getTransportFailedCount() != request.transportFailedCount()
                || existing.getDurationMs() != request.durationMs()
                || existing.getChannels().size() != request.channels().size()) {
            return false;
        }
        return request.channels().stream().allMatch(channel -> existing.getChannels().stream().anyMatch(saved ->
                saved.getChannel().equals(channel.channel().trim().toLowerCase(Locale.ROOT))
                        && saved.getOutcome() == channel.outcome()
                        && saved.getValidatedArticleCount() == channel.validatedArticleCount()
                        && saved.getSourceInvalidCount() == channel.sourceInvalidCount()
                        && saved.getSuccessfulUnits() == channel.successfulUnits()
                        && saved.getPartialUnits() == channel.partialUnits()
                        && saved.getEmptyUnits() == channel.emptyUnits()
                        && saved.getFailedUnits() == channel.failedUnits()
        ));
    }

    private long add(long... values) {
        try {
            long result = 0;
            for (long value : values) {
                result = Math.addExact(result, value);
            }
            return result;
        } catch (ArithmeticException error) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "수량 합계가 허용 범위를 초과했습니다.", error);
        }
    }

    private LocalDateTime toUtcLocalDateTime(OffsetDateTime value) {
        LocalDateTime utc = value.withOffsetSameInstant(ZoneOffset.UTC).toLocalDateTime();
        return utc.withNano((utc.getNano() / 1_000) * 1_000);
    }

    private void validateRunId(String runId) {
        if (!runId.matches("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")) {
            badRequest("runId는 UUID 형식이어야 합니다.");
        }
    }

    private void badRequest(String message) {
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, message);
    }

    private record ValidatedRun(
            long sourceInvalidCount,
            long successfulChannelCount,
            long partialChannelCount,
            long emptyChannelCount,
            long failedChannelCount,
            long successfulUnitCount,
            long partialUnitCount,
            long emptyUnitCount,
            long failedUnitCount
    ) {
    }
}
