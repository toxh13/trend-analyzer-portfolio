package com.example.backendspring.service;

import com.example.backendspring.dto.CrawlerKeywordRequest;
import com.example.backendspring.dto.CrawlerKeywordResponse;
import com.example.backendspring.entity.CrawlerKeyword;
import com.example.backendspring.entity.CrawlerKeywordType;
import com.example.backendspring.repository.CrawlerKeywordRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 관리자 키워드 관리 비즈니스 로직입니다.
 * 최소 관리자 페이지에서는 목록 조회, 등록, 활성/비활성 전환만 제공합니다.
 */
@Service
@RequiredArgsConstructor
public class CrawlerKeywordService {

    private final CrawlerKeywordRepository crawlerKeywordRepository;

    /**
     * 관리자 페이지 키워드 목록을 조회합니다.
     */
    public List<CrawlerKeywordResponse> getKeywords() {
        return crawlerKeywordRepository.findAllByOrderByPriorityDescKeywordAsc()
                .stream()
                .map(CrawlerKeywordResponse::from)
                .toList();
    }

    /**
     * 새 키워드를 등록합니다.
     * 중복 키워드는 운영 데이터 혼선을 만들 수 있으므로 등록 전에 차단합니다.
     */
    @Transactional
    public CrawlerKeywordResponse createKeyword(CrawlerKeywordRequest request) {
        String normalizedKeyword = normalizeKeyword(request.keyword());

        if (crawlerKeywordRepository.existsByKeyword(normalizedKeyword)) {
            throw new IllegalArgumentException("이미 등록된 키워드입니다: " + normalizedKeyword);
        }

        LocalDateTime now = LocalDateTime.now();
        CrawlerKeyword keyword = CrawlerKeyword.builder()
                .keyword(normalizedKeyword)
                .category(normalizeNullable(request.category()))
                .active(request.active() != null ? request.active() : true)
                .priority(request.priority() != null ? request.priority() : 0)
                .notionEnabled(request.notionEnabled() != null ? request.notionEnabled() : true)
                .keywordType(request.keywordType() != null ? request.keywordType() : CrawlerKeywordType.TRACKING)
                .createdAt(now)
                .updatedAt(now)
                .build();

        return CrawlerKeywordResponse.from(crawlerKeywordRepository.save(keyword));
    }

    /**
     * 키워드 활성/비활성 상태를 전환합니다.
     * 삭제 대신 비활성화를 사용하면 과거 운영 설정을 추적하기 쉽습니다.
     */
    @Transactional
    public CrawlerKeywordResponse toggleKeyword(Long id) {
        CrawlerKeyword keyword = crawlerKeywordRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("키워드를 찾을 수 없습니다. id=" + id));

        keyword.setActive(!Boolean.TRUE.equals(keyword.getActive()));
        keyword.setUpdatedAt(LocalDateTime.now());

        return CrawlerKeywordResponse.from(keyword);
    }

    /**
     * Python 크롤러나 내부 로직이 사용할 활성 키워드만 조회합니다.
     */
    public List<CrawlerKeywordResponse> getActiveKeywords() {
        return crawlerKeywordRepository.findByActiveTrueOrderByPriorityDescKeywordAsc()
                .stream()
                .map(CrawlerKeywordResponse::from)
                .toList();
    }
    /**
     * 저장/집계에서 제외할 차단 키워드 목록을 Set으로 조회합니다.
     * 비교 안정성을 위해 trim + lowercase 형태로 변환합니다.
     */
    public Set<String> getActiveBlockedKeywordSet() {
        return crawlerKeywordRepository
                .findByKeywordTypeAndActiveTrueOrderByPriorityDescKeywordAsc(CrawlerKeywordType.BLOCKED)
                .stream()
                .map(CrawlerKeyword::getKeyword)
                .map(this::normalizeForCompare)
                .filter(keyword -> !keyword.isBlank())
                .collect(Collectors.toSet());
    }

    public Set<String> getInactiveKeywordSet() {
        return crawlerKeywordRepository
                .findByActiveFalseOrderByPriorityDescKeywordAsc()
                .stream()
                .map(CrawlerKeyword::getKeyword)
                .map(this::normalizeForCompare)
                .filter(keyword -> !keyword.isBlank())
                .collect(Collectors.toSet());
    }

    /**
     * 키워드 비교용 정규화 함수입니다.
     * 예: " AI "와 "ai"를 같은 값으로 비교하기 위해 사용합니다.
     */
    private String normalizeForCompare(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String normalizeKeyword(String value) {
        return value == null ? "" : value.trim();
    }

    private String normalizeNullable(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }
}
