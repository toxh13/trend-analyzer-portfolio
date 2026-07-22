package com.example.backendspring.service;

import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.KeywordAliasRepository;
import com.example.backendspring.repository.KeywordGroupRepository;
import com.example.backendspring.repository.KeywordMergeSuggestionRepository;
import com.example.backendspring.entity.KeywordGroup;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.web.client.RestTemplateBuilder;

import java.util.List;
import java.util.Set;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class KeywordMergeSuggestionBatchServiceTest {

    @Mock
    private ArticleKeywordRepository articleKeywordRepository;
    @Mock
    private KeywordAliasRepository keywordAliasRepository;
    @Mock
    private KeywordGroupRepository keywordGroupRepository;
    @Mock
    private KeywordMergeSuggestionRepository keywordMergeSuggestionRepository;
    @Mock
    private CrawlerKeywordService crawlerKeywordService;
    @Mock
    private KeywordNormalizer keywordNormalizer;
    @Mock
    private RestTemplateBuilder restTemplateBuilder;

    @Test
    void limitsModelInputToTwoHundredCandidates() {
        KeywordGroup group = KeywordGroup.builder()
                .id(1L)
                .canonicalKeyword("AI")
                .active(true)
                .build();
        List<String> keywords = IntStream.range(0, 201)
                .mapToObj(index -> "keyword-" + index)
                .toList();
        when(keywordGroupRepository.findByActiveTrueOrderByCanonicalKeywordAsc()).thenReturn(List.of(group));
        when(articleKeywordRepository.findTopKeywordsByMentionCountPublishedAfter(any())).thenReturn(keywords);
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of());
        when(crawlerKeywordService.getInactiveKeywordSet()).thenReturn(Set.of());
        when(keywordNormalizer.normalize(any())).thenAnswer(invocation -> invocation.getArgument(0));
        when(keywordAliasRepository.existsByNormalizedKeyword(any())).thenReturn(false);
        when(keywordMergeSuggestionRepository.existsByNormalizedSourceKeywordAndTargetGroupIdAndStatusIn(any(), any(), any()))
                .thenReturn(false);

        KeywordMergeSuggestionBatchService.CandidateSelection selection = service().loadCandidateKeywords(1L, "AI");

        assertThat(selection.candidates()).hasSize(200);
    }

    private KeywordMergeSuggestionBatchService service() {
        return new KeywordMergeSuggestionBatchService(
                articleKeywordRepository,
                keywordAliasRepository,
                keywordGroupRepository,
                keywordMergeSuggestionRepository,
                crawlerKeywordService,
                keywordNormalizer,
                restTemplateBuilder
        );
    }
}
