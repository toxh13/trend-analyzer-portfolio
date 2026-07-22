package com.example.backendspring.repository;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.jpa.repository.Query;

import java.time.LocalDateTime;
import java.util.Collection;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleRepositoryEvidenceQueryContractTest {

    @Test
    @DisplayName("기사 근거 SQL은 반개구간, alias 중복 제거, 최신순 계약을 유지한다")
    void evidenceQueryKeepsRequiredSqlContract() throws NoSuchMethodException {
        Query query = ArticleRepository.class.getMethod(
                "findEvidenceByKeywordsWithinWindow",
                Collection.class,
                LocalDateTime.class,
                LocalDateTime.class,
                org.springframework.data.domain.Pageable.class
        ).getAnnotation(Query.class);

        String sql = query.value().replaceAll("\\s+", " ").toLowerCase();

        assertThat(query.nativeQuery()).isTrue();
        assertThat(sql).contains("a.published_at >= :startdate");
        assertThat(sql).contains("a.published_at < :enddate");
        assertThat(sql).contains("exists (");
        assertThat(sql).contains("k.keyword in (:keywords)");
        assertThat(sql).contains("order by a.published_at desc, a.id desc");
    }
}
