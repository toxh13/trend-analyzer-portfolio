package com.example.backendspring.service;

import com.example.backendspring.dto.KeywordRecommendationRequest;
import com.example.backendspring.dto.KeywordRecommendationResponse;
import com.example.backendspring.entity.KeywordGroup;
import com.example.backendspring.entity.KeywordMergeSuggestion;
import com.example.backendspring.entity.KeywordMergeSuggestionStatus;
import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.KeywordAliasRepository;
import com.example.backendspring.repository.KeywordGroupRepository;
import com.example.backendspring.repository.KeywordMergeSuggestionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class KeywordMergeSuggestionBatchService {

    private static final int LOOKBACK_DAYS = 7;
    private static final int MAX_CANDIDATE_COUNT = 200;
    private static final double SIMILARITY_THRESHOLD = 0.85;
    private static final int TOP_K = 3;
    private static final String FALLBACK_MODEL_NAME = "keyword-embedding-recommender";
    private static final String FALLBACK_MODEL_VERSION = "unknown";

    private final ArticleKeywordRepository articleKeywordRepository;
    private final KeywordAliasRepository keywordAliasRepository;
    private final KeywordGroupRepository keywordGroupRepository;
    private final KeywordMergeSuggestionRepository keywordMergeSuggestionRepository;
    private final CrawlerKeywordService crawlerKeywordService;
    private final KeywordNormalizer keywordNormalizer;
    private final RestTemplateBuilder restTemplateBuilder;

    @Value("${app.ai.keyword-recommender-url}")
    private String keywordRecommenderUrl;

    @Value("${app.security.crawler-api-key}")
    private String crawlerApiKey;

    @Transactional(readOnly = true)
    public CandidateSelection loadCandidateKeywords(Long targetGroupId, String targetKeyword) {
        List<KeywordGroup> targetGroups = keywordGroupRepository.findByActiveTrueOrderByCanonicalKeywordAsc();
        if (targetGroups.isEmpty()) {
            return new CandidateSelection(List.of(), targetGroupId, targetKeyword);
        }

        return new CandidateSelection(loadCandidateKeywords(targetGroups, targetGroupId), targetGroupId, targetKeyword);
    }

    private List<KeywordRecommendationRequest.CandidateKeyword> loadCandidateKeywords(
            List<KeywordGroup> targetGroups,
            Long targetGroupId
    ) {
        LocalDateTime startDate = LocalDateTime.now().minusDays(LOOKBACK_DAYS);
        var blockedKeywords = crawlerKeywordService.getActiveBlockedKeywordSet()
                .stream()
                .map(keywordNormalizer::normalize)
                .collect(Collectors.toSet());
        var inactiveCrawlerKeywords = crawlerKeywordService.getInactiveKeywordSet()
                .stream()
                .map(keywordNormalizer::normalize)
                .collect(Collectors.toSet());
        var canonicalKeywords = targetGroups.stream()
                .map(KeywordGroup::getCanonicalKeyword)
                .map(keywordNormalizer::normalize)
                .collect(Collectors.toSet());
        var reviewedStatuses = EnumSet.allOf(KeywordMergeSuggestionStatus.class);

        return articleKeywordRepository.findTopKeywordsByMentionCountPublishedAfter(startDate)
                .stream()
                .filter(rawKeyword -> rawKeyword != null && !rawKeyword.isBlank())
                .map(String::trim)
                .map(rawKeyword -> new KeywordRecommendationRequest.CandidateKeyword(
                        rawKeyword,
                        keywordNormalizer.normalize(rawKeyword)
                ))
                .filter(candidate -> !candidate.normalizedKeyword().isBlank())
                .filter(candidate -> !blockedKeywords.contains(candidate.normalizedKeyword()))
                .filter(candidate -> !inactiveCrawlerKeywords.contains(candidate.normalizedKeyword()))
                .filter(candidate -> !canonicalKeywords.contains(candidate.normalizedKeyword()))
                .filter(candidate -> !keywordAliasRepository.existsByNormalizedKeyword(candidate.normalizedKeyword()))
                .filter(candidate -> !keywordMergeSuggestionRepository.existsByNormalizedSourceKeywordAndTargetGroupIdAndStatusIn(
                        candidate.normalizedKeyword(),
                        targetGroupId,
                        reviewedStatuses
                ))
                .collect(Collectors.toMap(
                        KeywordRecommendationRequest.CandidateKeyword::normalizedKeyword,
                        Function.identity(),
                        (first, ignored) -> first,
                        LinkedHashMap::new
                ))
                .values()
                .stream()
                .limit(MAX_CANDIDATE_COUNT)
                .toList();
    }

    public KeywordRecommendationResponse requestRecommendations(CandidateSelection selection
    ) {
        KeywordRecommendationRequest request = new KeywordRecommendationRequest(
                selection.candidates(),
                new KeywordRecommendationRequest.TargetKeywordGroup(
                        selection.targetGroupId(),
                        selection.targetKeyword()
                ),
                SIMILARITY_THRESHOLD,
                TOP_K
        );

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-API-KEY", crawlerApiKey);

        RestTemplate restTemplate = restTemplateBuilder
                .setConnectTimeout(Duration.ofSeconds(5))
                .setReadTimeout(Duration.ofMinutes(5))
                .build();

        try {
            KeywordRecommendationResponse response = restTemplate.postForObject(
                    keywordRecommenderUrl,
                    new HttpEntity<>(request, headers),
                    KeywordRecommendationResponse.class
            );

            if (response == null) {
                throw new IllegalStateException("Keyword recommender returned an empty response.");
            }

            return response;
        } catch (RestClientException e) {
            throw new IllegalStateException("Keyword recommender request failed.", e);
        }
    }

    @Transactional
    public int saveRecommendations(KeywordRecommendationResponse response) {
        if (response.suggestions() == null || response.suggestions().isEmpty()) {
            return 0;
        }

        LocalDateTime now = LocalDateTime.now();
        String defaultModelName = defaultText(response.modelName(), FALLBACK_MODEL_NAME);
        String defaultModelVersion = defaultText(response.modelVersion(), FALLBACK_MODEL_VERSION);

        List<KeywordMergeSuggestion> suggestions = response.suggestions()
                .stream()
                .filter(Objects::nonNull)
                .filter(suggestion -> suggestion.targetGroupId() != null)
                .filter(suggestion -> suggestion.sourceKeyword() != null && !suggestion.sourceKeyword().isBlank())
                .filter(suggestion -> suggestion.normalizedSourceKeyword() != null && !suggestion.normalizedSourceKeyword().isBlank())
                .filter(suggestion -> suggestion.similarityScore() != null)
                .filter(suggestion -> suggestion.similarityScore().compareTo(BigDecimal.valueOf(SIMILARITY_THRESHOLD)) >= 0)
                .filter(suggestion -> !keywordMergeSuggestionRepository.existsByNormalizedSourceKeywordAndTargetGroupIdAndModelVersion(
                        suggestion.normalizedSourceKeyword(),
                        suggestion.targetGroupId(),
                        defaultText(suggestion.modelVersion(), defaultModelVersion)
                ))
                .map(suggestion -> KeywordMergeSuggestion.builder()
                        .sourceKeyword(suggestion.sourceKeyword().trim())
                        .normalizedSourceKeyword(suggestion.normalizedSourceKeyword())
                        .targetGroup(keywordGroupRepository.getReferenceById(suggestion.targetGroupId()))
                        .targetKeyword(defaultText(suggestion.targetKeyword(), ""))
                        .similarityScore(suggestion.similarityScore())
                        .reason(suggestion.reason())
                        .status(KeywordMergeSuggestionStatus.PENDING)
                        .modelName(defaultText(suggestion.modelName(), defaultModelName))
                        .modelVersion(defaultText(suggestion.modelVersion(), defaultModelVersion))
                        .createdAt(now)
                        .updatedAt(now)
                        .build())
                .toList();

        if (suggestions.isEmpty()) {
            return 0;
        }

        return keywordMergeSuggestionRepository.saveAll(suggestions).size();
    }

    private String defaultText(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value.trim();
    }

    public record CandidateSelection(
            List<KeywordRecommendationRequest.CandidateKeyword> candidates,
            Long targetGroupId,
            String targetKeyword
    ) {
    }
}
