package com.example.backendspring.service;

import com.example.backendspring.dto.CrawlingRequestDto;
import com.example.backendspring.dto.ExtractedKeywordDto;
import com.example.backendspring.entity.Article;
import com.example.backendspring.repository.ArticleRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CrawlingServiceTest {

    @Mock
    private ArticleRepository articleRepository;

    @Mock
    private CrawlerKeywordService crawlerKeywordService;

    @Test
    void saveCrawledDataPreservesKeywordOccurrenceCount() {
        CrawlingService service = new CrawlingService(articleRepository, crawlerKeywordService);
        CrawlingRequestDto request = new CrawlingRequestDto(
                "제목",
                "요약",
                "https://example.com/article",
                "테스트 언론사",
                "IT",
                LocalDateTime.of(2026, 7, 18, 10, 0),
                List.of(new ExtractedKeywordDto("인공지능", 5))
        );
        when(articleRepository.existsBySourceUrl(request.getSourceUrl())).thenReturn(false);
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of());
        when(articleRepository.save(any(Article.class))).thenAnswer(invocation -> invocation.getArgument(0));

        service.saveCrawledData(request);

        ArgumentCaptor<Article> captor = ArgumentCaptor.forClass(Article.class);
        verify(articleRepository).save(captor.capture());
        assertThat(captor.getValue().getKeywords()).hasSize(1);
        assertThat(captor.getValue().getKeywords().get(0).getKeyword()).isEqualTo("인공지능");
        assertThat(captor.getValue().getKeywords().get(0).getWeight()).isEqualTo(5);
    }

    @Test
    void saveCrawledDataRejectsMissingPublishedAtInsteadOfUsingCurrentTime() {
        CrawlingService service = new CrawlingService(articleRepository, crawlerKeywordService);
        CrawlingRequestDto request = new CrawlingRequestDto(
                "제목",
                "요약",
                "https://example.com/article",
                "테스트 언론사",
                "IT",
                null,
                List.of()
        );

        assertThatThrownBy(() -> service.saveCrawledData(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("기사 필수 데이터가 누락되었습니다.");
        verifyNoInteractions(articleRepository, crawlerKeywordService);
    }

    @Test
    void saveCrawledDataRejectsBlankSummary() {
        CrawlingService service = new CrawlingService(articleRepository, crawlerKeywordService);
        CrawlingRequestDto request = new CrawlingRequestDto(
                "제목",
                " ",
                "https://example.com/article",
                "테스트 언론사",
                "IT",
                LocalDateTime.of(2026, 7, 19, 12, 0),
                List.of()
        );

        assertThatThrownBy(() -> service.saveCrawledData(request))
                .isInstanceOf(IllegalArgumentException.class);
        verifyNoInteractions(articleRepository, crawlerKeywordService);
    }
}
