package com.example.backendspring.repository;

import com.example.backendspring.entity.KeywordAlias;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface KeywordAliasRepository extends JpaRepository<KeywordAlias, Long> {

    /**
     * alias cache 로딩용입니다.
     *
     * @EntityGraph를 붙이는 이유:
     * - KeywordAlias.keywordGroup은 LAZY 로딩입니다.
     * - 캐시를 만들 때 alias.getKeywordGroup().getCanonicalKeyword()를 읽어야 합니다.
     * - 트랜잭션 밖에서 LazyInitializationException이 날 수 있으므로 keywordGroup을 함께 조회합니다.
     */
    @EntityGraph(attributePaths = "keywordGroup")
    List<KeywordAlias> findByActiveTrue();

    /**
     * 특정 대표 키워드 그룹에 연결된 alias 목록입니다.
     */
    List<KeywordAlias> findByKeywordGroupIdOrderByRawKeywordAsc(Long keywordGroupId);

    /**
     * alias 중복 등록 방지용입니다.
     */
    Optional<KeywordAlias> findByNormalizedKeyword(String normalizedKeyword);

    boolean existsByNormalizedKeyword(String normalizedKeyword);
}
