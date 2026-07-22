package com.example.backendspring.service;

import com.example.backendspring.dto.TrendHistoryEvidenceResponseDto;
import com.example.backendspring.entity.Article;
import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.ArticleRepository;
import com.example.backendspring.repository.TrendMetricRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Pageable;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TrendEvidenceServiceTest {

    @Mock
    private TrendMetricRepository trendMetricRepository;
    @Mock
    private ArticleRepository articleRepository;
    @Mock
    private ArticleKeywordRepository articleKeywordRepository;
    @Mock
    private KeywordAliasCacheService keywordAliasCacheService;
    @Mock
    private Clock clock;

    @InjectMocks
    private TrendService trendService;

    @Test
    @SuppressWarnings("unchecked")
    @DisplayName("기사 근거는 서울 날짜 반개구간과 alias를 사용해 키워드별 최신 기사만 반환한다")
    void getHistoryEvidenceUsesSeoulHalfOpenWindowAliasesAndLimit() {
        LocalDate date = LocalDate.of(2026, 7, 19);
        Set<String> firstAliases = Set.of("AI", "인공지능");
        Set<String> secondAliases = Set.of("반도체", "세미컨덕터");
        Article newest = article(2L, "최신 기사", "최신 요약", LocalDateTime.of(2026, 7, 19, 23, 59));
        Article older = article(1L, "이전 기사", "이전 요약", LocalDateTime.of(2026, 7, 19, 0, 0));

        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("반도체")).thenReturn("반도체");
        when(keywordAliasCacheService.resolveSearchKeywords("인공지능")).thenReturn(firstAliases);
        when(keywordAliasCacheService.resolveSearchKeywords("반도체")).thenReturn(secondAliases);
        when(articleRepository.findEvidenceByKeywordsWithinWindow(anyCollection(), any(), any(), any()))
                .thenReturn(List.of(newest, older), List.of());

        TrendHistoryEvidenceResponseDto response =
                trendService.getKeywordHistoryEvidence(" AI ", "반도체", date, 2);

        assertThat(response.getDate()).isEqualTo("2026-07-19");
        assertThat(response.getTimezone()).isEqualTo("Asia/Seoul");
        assertThat(response.getFirstCanonicalKeyword()).isEqualTo("인공지능");
        assertThat(response.getSecondCanonicalKeyword()).isEqualTo("반도체");
        assertThat(response.getFirstArticles())
                .extracting(article -> article.getId(), article -> article.getTitle())
                .containsExactly(
                        org.assertj.core.groups.Tuple.tuple(2L, "최신 기사"),
                        org.assertj.core.groups.Tuple.tuple(1L, "이전 기사")
                );
        assertThat(response.getFirstArticles().get(0).getSummary()).isEqualTo("최신 요약");
        assertThat(response.getFirstArticles().get(0).getSource()).isEqualTo("테스트 언론사");
        assertThat(response.getFirstArticles().get(0).getPublishedAt())
                .isEqualTo(newest.getPublishedAt().atZone(java.time.ZoneId.of("Asia/Seoul")).toOffsetDateTime());
        assertThat(response.getFirstArticles().get(0).getSourceUrl()).isEqualTo("https://example.com/2");
        assertThat(response.getSecondArticles()).isEmpty();

        ArgumentCaptor<Collection<String>> keywordCaptor = ArgumentCaptor.forClass(Collection.class);
        ArgumentCaptor<LocalDateTime> startCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        ArgumentCaptor<LocalDateTime> endCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        verify(articleRepository, org.mockito.Mockito.times(2)).findEvidenceByKeywordsWithinWindow(
                keywordCaptor.capture(), startCaptor.capture(), endCaptor.capture(), pageableCaptor.capture()
        );
        assertThat(keywordCaptor.getAllValues()).containsExactly(firstAliases, secondAliases);
        assertThat(startCaptor.getAllValues()).containsOnly(LocalDateTime.of(2026, 7, 19, 0, 0));
        assertThat(endCaptor.getAllValues()).containsOnly(LocalDateTime.of(2026, 7, 20, 0, 0));
        assertThat(pageableCaptor.getAllValues()).allMatch(pageable -> pageable.getPageSize() == 2);
    }

    @Test
    @DisplayName("같은 대표 키워드의 기사 근거 비교는 400 오류로 차단한다")
    void getHistoryEvidenceRejectsSameCanonicalKeyword() {
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("인공지능")).thenReturn("인공지능");

        assertThatThrownBy(() -> trendService.getKeywordHistoryEvidence(
                "AI", "인공지능", LocalDate.of(2026, 7, 19), 5
        ))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("같은 대표 키워드");

        verify(articleRepository, never())
                .findEvidenceByKeywordsWithinWindow(anyCollection(), any(), any(), any());
    }

    @Test
    @DisplayName("기사 근거 limit가 1에서 5 사이가 아니면 400 오류를 반환한다")
    void getHistoryEvidenceRejectsLimitOutsideRange() {
        LocalDate date = LocalDate.of(2026, 7, 19);

        assertThatThrownBy(() -> trendService.getKeywordHistoryEvidence("AI", "반도체", date, 0))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("1~5");
        assertThatThrownBy(() -> trendService.getKeywordHistoryEvidence("AI", "반도체", date, 6))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("1~5");
    }

    private Article article(Long id, String title, String summary, LocalDateTime publishedAt) {
        return Article.builder()
                .id(id)
                .title(title)
                .summary(summary)
                .source("테스트 언론사")
                .sourceUrl("https://example.com/" + id)
                .category("IT/과학")
                .publishedAt(publishedAt)
                .build();
    }
}
