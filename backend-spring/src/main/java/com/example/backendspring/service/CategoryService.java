package com.example.backendspring.service;

import com.example.backendspring.dto.CategoryResponseDto;
import com.example.backendspring.repository.ArticleRepository;
import com.example.backendspring.repository.TrendMetricRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * CategoryService - 대시보드 카테고리 필터 목록을 DB 기준으로 구성하는 서비스입니다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class CategoryService {
    private final ArticleRepository articleRepository;
    private final TrendMetricRepository trendMetricRepository;

    /**
     * articles에 저장된 실제 카테고리와 trend_metrics의 카테고리별 개수를 합쳐 반환합니다.
     * 새 크롤링 카테고리가 DB에 저장되면 프론트엔드 필터 목록에도 자동 반영됩니다.
     */
    public List<CategoryResponseDto> getAvailableCategories() {
        Map<String, Long> categoryCountMap = new TreeMap<>();

        // 새로 수집된 카테고리도 필터 후보에 포함합니다.
        for (String rawCategory : articleRepository.findDistinctCategories()) {
            String category = normalizeCategoryName(rawCategory);
            if (category != null) {
                categoryCountMap.putIfAbsent(category, 0L);
            }
        }

        // 트렌드 집계 결과가 있으면 카테고리별 개수를 갱신합니다.
        for (Object[] row : trendMetricRepository.findCategoryCounts()) {
            String category = normalizeCategoryName(row[0]);
            if (category == null) {
                continue;
            }

            long trendCount = row[1] instanceof Number ? ((Number) row[1]).longValue() : 0L;
            categoryCountMap.put(category, trendCount);
        }

        return categoryCountMap.entrySet().stream()
                .map(entry -> CategoryResponseDto.builder()
                        .id(entry.getKey())
                        .label(entry.getKey())
                        .trendCount(entry.getValue())
                        .build())
                .collect(Collectors.toList());
    }

    /**
     * 카테고리 문자열의 앞뒤 공백을 제거하고 빈 값은 제외합니다.
     */
    private String normalizeCategoryName(Object rawCategory) {
        if (rawCategory == null) {
            return null;
        }

        String category = String.valueOf(rawCategory).trim();
        return category.isEmpty() ? null : category;
    }
}
