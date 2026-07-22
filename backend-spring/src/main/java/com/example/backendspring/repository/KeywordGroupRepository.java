package com.example.backendspring.repository;

import com.example.backendspring.entity.KeywordGroup;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface KeywordGroupRepository extends JpaRepository<KeywordGroup, Long> {

    /**
     * 관리자 화면에서 활성 그룹을 대표 키워드명 기준으로 조회합니다.
     */
    List<KeywordGroup> findByActiveTrueOrderByCanonicalKeywordAsc();

    /**
     * 대표 키워드 중복 등록을 막기 위한 조회입니다.
     */
    boolean existsByNormalizedCanonicalKeyword(String normalizedCanonicalKeyword);

    Optional<KeywordGroup> findByNormalizedCanonicalKeyword(String normalizedCanonicalKeyword);
}