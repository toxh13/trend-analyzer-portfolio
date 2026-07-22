package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 관리자가 지정하는 수집/관심 키워드입니다.
 * article_keywords는 기사에서 추출된 키워드이고,
 * crawler_keywords는 관리자가 직접 제어하는 운영 키워드입니다.
 */
@Entity
@Table(name = "crawler_keywords")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CrawlerKeyword {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "crawler_keyword_seq")
    @SequenceGenerator(
            name = "crawler_keyword_seq",
            sequenceName = "CRAWLER_KEYWORD_SEQ",
            allocationSize = 1
    )
    private Long id;

    @Column(nullable = false, unique = true, length = 100)
    private String keyword;

    @Column(length = 100)
    private String category;

    @Column(nullable = false)
    private Boolean active;

    @Column(nullable = false)
    private Integer priority;

    @Column(name = "notion_enabled", nullable = false)
    private Boolean notionEnabled;

    @Enumerated(EnumType.STRING)
    @Column(name = "keyword_type", nullable = false, length = 30)
    private CrawlerKeywordType keywordType;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}