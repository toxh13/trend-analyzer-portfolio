package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
@Builder
@Entity
@Table(name="articles")
@NoArgsConstructor
@AllArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class Article {

    /**
     * [최적화] 오라클 인프라 환경에 맞춰 전용 Sequence Generator 매핑
     * 시퀀스 캐시 및 얼로케이션 크기를 조율하여 대량 데이터 적재 성능 최적화
     */
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "article_seq")
    @SequenceGenerator(name = "article_seq", sequenceName = "ARTICLE_SEQ", allocationSize = 1)
    private Long id;

    @Column(nullable = false, length = 1000)
    private String title; // 기사의 제목

    /**
     * [보안 및 데이터 유실 방지] 대용량 기사 요약본 처리를 위한 CLOB 객체 정의
     */
    @Lob
    @Column(nullable = false, columnDefinition = "CLOB")
    private String summary; // 기사의 요약

    @Column(name="source_url", nullable = false, unique = true, length = 1000)
    private String sourceUrl; // 기사 주소 (중복 방지용 유니크 인덱스 제약)

    @Column(nullable = false)
    private String source; // 기사의 출처 (네이버, 다음 등)

    @Column(nullable = false)
    private String category; // 뉴스 카테고리 (IT/과학, 경제 등)

    @Column(name="published_at")
    private LocalDateTime publishedAt; // 언론사 원본 기사 발행일

    @Column(name="crawled_at")
    private LocalDateTime crawledAt; // 시스템 수집 및 적재 시간

    /**
     * 🌟 [복구] article_keywords 테이블과의 1:N 양방향 연관관계 바인딩
     * * [최적화] 대규모 트래픽 환경에서 N+1 성능 성능 헬을 차단하기 위해 FetchType.LAZY(지연 로딩) 설정.
     * [보안/무결성] CascadeType.ALL을 통해 기사(Article) 저장 시 추출된 키워드(ArticleKeyword)가 영속성 컨텍스트 체인을 타고
     * 물리 DB에 함께 원자적(Atomic)으로 벌크 적재되도록 보장합니다.
     */
    @Builder.Default
    @OneToMany(mappedBy = "article", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<ArticleKeyword> keywords = new ArrayList<>();
}