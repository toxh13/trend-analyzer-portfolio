package com.example.backendspring.service;

import com.example.backendspring.dto.CrawlingRequestDto;
import com.example.backendspring.dto.ExtractedKeywordDto;
import com.example.backendspring.entity.Article;
import com.example.backendspring.entity.ArticleKeyword;
import com.example.backendspring.repository.ArticleRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
@Service
@RequiredArgsConstructor
@Slf4j
public class CrawlingService {
    private final ArticleRepository articleRepository;
    private final CrawlerKeywordService crawlerKeywordService;
    // [보안] 대소문자 구분 없이 악성 태그(<script>, <iframe> 등) 및 인라인 자바스크립트 스크립트 패턴 사전 컴파일
    // 최적화: 매번 호출될 때마다 Pattern.compile()을 실행하면 컴파일 연산 낭비가 심하므로 static final 상수로 메모리에 미리 static 로드하여 GC 부하를 최소화합니다.
    private static final Pattern ANTI_XSS_SCRIPT_PATTERN = Pattern.compile("<script[^>]*>(.*?)</script>", Pattern.CASE_INSENSITIVE);
    private static final Pattern ANTI_XSS_IFRAME_PATTERN = Pattern.compile("<iframe[^>]*>(.*?)</iframe>", Pattern.CASE_INSENSITIVE);
    private static final Pattern ANTI_XSS_EVENT_PATTERN = Pattern.compile("on\\w+\\s*=", Pattern.CASE_INSENSITIVE);


    /**
     * [보안 주석] Stored XSS 방어용 인메모리 문자열 치환 유틸리티
     * - 최적화: String.replaceAll()은 내부적으로 매번 새로운 정규식 객체를 생성하므로
     * 컴파일 자원 낭비가 큽니다. 사전 정의한 컴파일 패턴의 Matcher 인터페이스를 돌려 String Pool 자원을 최적화합니다.
     */
    private String cleanXssHazards(String rawInput) {
        if (rawInput == null || rawInput.isBlank()) {
            return rawInput;
        }

        // 1. 스크립트 실행 태그 완전 거부 및 공백화
        String cleaned = ANTI_XSS_SCRIPT_PATTERN.matcher(rawInput).replaceAll("");
        // 2. 외부 피싱 페이지 임베딩용 iframe 도려내기
        cleaned = ANTI_XSS_IFRAME_PATTERN.matcher(cleaned).replaceAll("");
        // 3. HTML 요소 내 인라인 이벤트 가드 무력화 (ex: <img src=x onerror=alert(1)> 방어)
        cleaned = ANTI_XSS_EVENT_PATTERN.matcher(cleaned).replaceAll("x-prevented-event=");

        // 4. 기본적인 HTML 엔티티 이스케이프 안전 장치 추가
        cleaned = cleaned.replace("<", "&lt;")
                .replace(">", "&gt;");

        return cleaned;
    }

    /*
     * 💡 [추가 보완 필요 주석]
     * 현재는 정규표현식 기반의 가벼운 화이트리스트/블랙리스트 혼합 정제 기법을 직접 구현하여 구동 오버헤드를 낮췄음.
     * 추후 Phase 2 챗봇 고도화 단계에서 사용자가 직접 마크다운 문서나 HTML 서식을 첨부해 업로드하는 기능이 도입된다면,
     * 더 고도화되고 검증된 Naver Lucy XSS Filter 라이브러리를 build.gradle에 도입하여 필터 체인 레벨로 격상 보완해야 함.
     */
    @Transactional
    public void saveCrawledData(CrawlingRequestDto crawlingDto) {
        validateRequiredArticleData(crawlingDto);

        if(articleRepository.existsBySourceUrl(crawlingDto.getSourceUrl())) {
            log.info("중복된 기사입니다. 스킵합니다. {}", crawlingDto.getSourceUrl());
            return;
        }
        String safeTitle = cleanXssHazards(crawlingDto.getTitle());
        String safeSummary = cleanXssHazards(crawlingDto.getSummary());
        LocalDateTime now = LocalDateTime.now();

        Article article = Article.builder()
                .title(safeTitle)
                .summary(safeSummary)
                .sourceUrl(crawlingDto.getSourceUrl())
                .source(crawlingDto.getSource())
                .category(crawlingDto.getCategory())
                .publishedAt(crawlingDto.getPublishedAt())
                .crawledAt(now) // 기사 보관 정책 30일 계산 기준값입니다.
                .keywords(new ArrayList<>())
                .build();

        if (crawlingDto.getKeywords() != null && !crawlingDto.getKeywords().isEmpty()) {
            // 관리자 페이지에서 BLOCKED로 등록된 키워드 목록을 조회합니다.
            Set<String> blockedKeywords = crawlerKeywordService.getActiveBlockedKeywordSet();

            // 정규화한 키워드별로 묶어 같은 키워드가 중복 저장되지 않게 합니다.
            Map<String, ExtractedKeywordDto> uniqueKeywords = new LinkedHashMap<>();
            for (ExtractedKeywordDto extractedKeyword : crawlingDto.getKeywords()) {
                if (extractedKeyword == null || extractedKeyword.getKeyword() == null) {
                    continue;
                }

                String normalizedKeyword = normalizeForCompare(extractedKeyword.getKeyword());
                uniqueKeywords.merge(
                        normalizedKeyword,
                        extractedKeyword,
                        (existing, duplicate) -> new ExtractedKeywordDto(
                                existing.getKeyword(),
                                Math.max(1, existing.getOccurrenceCount())
                                        + Math.max(1, duplicate.getOccurrenceCount())
                        )
                );
            }

            for (ExtractedKeywordDto extractedKeyword : uniqueKeywords.values()) {
                String keyword = extractedKeyword.getKeyword().trim();

                // 빈 문자열은 저장하지 않습니다.
                if (keyword.isBlank()) {
                    continue;
                }

                // 관리자 차단 키워드는 article_keywords에 저장하지 않습니다.
                if (blockedKeywords.contains(normalizeForCompare(keyword))) {
                    log.info("차단 키워드 저장 제외: {}", keyword);
                    continue;
                }

                ArticleKeyword articleKeyword = ArticleKeyword.builder()
                        .keyword(keyword)
                        .article(article)
                        // weight에는 키워드가 이 기사 안에서 추출된 횟수를 저장합니다.
                        .weight(Math.max(1, extractedKeyword.getOccurrenceCount()))
                        .createdAt(now)
                        .build();

                article.getKeywords().add(articleKeyword);
            }
        }
        articleRepository.save(article);

        log.info("뉴스 적재 완료 : {}", crawlingDto.getTitle());
    }

    private void validateRequiredArticleData(CrawlingRequestDto crawlingDto) {
        if (crawlingDto == null
                || isBlank(crawlingDto.getTitle())
                || isBlank(crawlingDto.getSummary())
                || isBlank(crawlingDto.getSourceUrl())
                || isBlank(crawlingDto.getSource())
                || isBlank(crawlingDto.getCategory())
                || crawlingDto.getPublishedAt() == null) {
            throw new IllegalArgumentException("기사 필수 데이터가 누락되었습니다.");
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
    /**
     * 키워드 비교용 정규화 함수입니다.
     * 공백 제거 + 소문자 변환으로 영문 키워드 비교 안정성을 높입니다.
     */
    private String normalizeForCompare(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }


}
