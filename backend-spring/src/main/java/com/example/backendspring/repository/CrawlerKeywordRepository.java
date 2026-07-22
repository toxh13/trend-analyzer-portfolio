package com.example.backendspring.repository;

import com.example.backendspring.entity.CrawlerKeyword;
import com.example.backendspring.entity.CrawlerKeywordType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * 관리자 지정 키워드 저장소입니다.
 * 트렌드 추출 키워드(article_keywords)와 운영자가 관리하는 키워드(crawler_keywords)를 분리합니다.
 */
public interface CrawlerKeywordRepository extends JpaRepository<CrawlerKeyword, Long> {

    /**
     * 중복 키워드 등록을 방지하기 위해 키워드명으로 존재 여부를 확인합니다.
     */
    boolean existsByKeyword(String keyword);

    /**
     * 수정 시 자기 자신을 제외한 중복 키워드가 있는지 확인합니다.
     */
    boolean existsByKeywordAndIdNot(String keyword, Long id);

    /**
     * 키워드 목록을 우선순위가 높은 순서로 조회합니다.
     */
    List<CrawlerKeyword> findAllByOrderByPriorityDescKeywordAsc();

    /**
     * Python 크롤러 또는 향후 필터링 로직에서 활성 키워드만 조회할 때 사용합니다.
     */
    List<CrawlerKeyword> findByActiveTrueOrderByPriorityDescKeywordAsc();

    List<CrawlerKeyword> findByActiveFalseOrderByPriorityDescKeywordAsc();

    Optional<CrawlerKeyword> findByKeyword(String keyword);

    /**
     * 특정 타입의 활성 키워드만 조회합니다.
     * 예: active=true 이면서 keywordType=BLOCKED 인 키워드 목록 조회
     */
    List<CrawlerKeyword> findByKeywordTypeAndActiveTrueOrderByPriorityDescKeywordAsc(
            CrawlerKeywordType keywordType
    );  
}
