package com.example.backendspring.service;

import com.example.backendspring.repository.KeywordAliasRepository;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * 활성 alias를 메모리에 올려두는 조회 캐시입니다.
 *
 * <p>트렌드 화면은 키워드마다 alias 해석을 자주 수행합니다. 활성 alias 전체를
 * 메모리 맵에 올려두면 키워드별 DB 조회를 피하면서 구조를 단순하게 유지할 수
 * 있습니다. alias를 변경하는 서비스는 같은 요청 흐름에서 {@link #reload()}를
 * 호출해 사용자가 변경된 병합 규칙을 즉시 보게 합니다.</p>
 */
@Service
@RequiredArgsConstructor
public class KeywordAliasCacheService {

    private final KeywordAliasRepository keywordAliasRepository;
    private final KeywordNormalizer keywordNormalizer;

    /**
     * 정규화된 alias를 대표 키워드 표시명으로 변환하는 맵입니다.
     *
     * <p>예: {@code ai -> Artificial Intelligence}</p>
     */
    private final Map<String, String> aliasMap = new ConcurrentHashMap<>();

    /**
     * 정규화된 대표 키워드별로 관련 기사와 히스토리 조회에 함께 사용할
     * 원본 키워드 묶음을 저장합니다.
     */
    private final Map<String, Set<String>> canonicalKeywordMap = new ConcurrentHashMap<>();

    /**
     * 애플리케이션 시작 직후 승인된 병합 규칙을 대시보드에서 사용할 수 있도록
     * alias 캐시를 초기 로딩합니다.
     */
    @PostConstruct
    public void loadOnStartup() {
        reload();
    }

    /**
     * 활성 alias만 기준으로 캐시를 다시 구성합니다.
     *
     * <p>새 맵을 먼저 만든 뒤 기존 맵의 내용을 교체하므로, 재로딩 중에도
     * 읽기 요청은 항상 유효한 데이터를 보게 됩니다.</p>
     */
    @Transactional(readOnly = true)
    public void reload() {
        Map<String, String> newAliasMap = new ConcurrentHashMap<>();
        Map<String, Set<String>> newCanonicalKeywordMap = new ConcurrentHashMap<>();

        keywordAliasRepository.findByActiveTrue()
                .forEach(alias -> {
                    String normalizedAlias = alias.getNormalizedKeyword();
                    String rawAlias = alias.getRawKeyword();
                    String canonicalKeyword = alias.getKeywordGroup().getCanonicalKeyword();
                    String normalizedCanonicalKeyword = keywordNormalizer.normalize(canonicalKeyword);

                    newAliasMap.put(normalizedAlias, canonicalKeyword);

                    Set<String> keywords = newCanonicalKeywordMap.computeIfAbsent(
                            normalizedCanonicalKeyword,
                            key -> ConcurrentHashMap.newKeySet()
                    );

                    keywords.add(canonicalKeyword);
                    keywords.add(rawAlias);
                });

        aliasMap.clear();
        aliasMap.putAll(newAliasMap);

        canonicalKeywordMap.clear();
        canonicalKeywordMap.putAll(newCanonicalKeywordMap);
    }

    /**
     * 원본 키워드가 활성 alias이면 대표 키워드를 반환하고, 등록되지 않은
     * 키워드는 그대로 반환합니다.
     */
    public String resolveKeyword(String rawKeyword) {
        String normalizedKeyword = keywordNormalizer.normalize(rawKeyword);
        return aliasMap.getOrDefault(normalizedKeyword, rawKeyword);
    }

    /**
     * 입력 키워드와 함께 검색해야 하는 모든 원본 키워드 묶음을 반환합니다.
     *
     * <p>사용자가 대표 키워드 상세 화면을 열면 관련 기사와 히스토리는 대표
     * 키워드뿐 아니라 모든 활성 alias까지 포함해야 합니다. 사용자가 alias를
     * 직접 열었을 때도 먼저 대표 키워드로 해석한 뒤 같은 묶음을 반환합니다.</p>
     */
    public Set<String> resolveSearchKeywords(String keyword) {
        String normalizedKeyword = keywordNormalizer.normalize(keyword);

        String canonicalKeyword = aliasMap.getOrDefault(normalizedKeyword, keyword);
        String normalizedCanonicalKeyword = keywordNormalizer.normalize(canonicalKeyword);

        Set<String> searchKeywords = new HashSet<>(
                canonicalKeywordMap.getOrDefault(normalizedCanonicalKeyword, Set.of())
        );

        searchKeywords.add(keyword);
        searchKeywords.add(canonicalKeyword);

        return searchKeywords.stream()
                .filter(value -> value != null && !value.isBlank())
                .collect(Collectors.toSet());
    }

    /**
     * 진단과 간단한 테스트에서 사용할 캐시 크기를 반환합니다.
     */
    public int size() {
        return aliasMap.size();
    }
}
