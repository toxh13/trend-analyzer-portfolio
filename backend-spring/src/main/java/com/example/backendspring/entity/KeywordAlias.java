package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 대표 키워드 그룹에 연결되는 alias 키워드 엔티티입니다.
 *
 * <p>관리자가 승인한 alias는 서로 다른 표기나 약어를 하나의 대시보드
 * 키워드로 합산하기 위해 사용됩니다.</p>
 */
@Entity
@Table(name = "keyword_aliases")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class KeywordAlias {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "keyword_alias_seq")
    @SequenceGenerator(
            name = "keyword_alias_seq",
            sequenceName = "KEYWORD_ALIAS_SEQ",
            allocationSize = 1
    )
    private Long id;

    /**
     * 이 alias가 연결된 대표 키워드 그룹입니다.
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "keyword_group_id", nullable = false)
    private KeywordGroup keywordGroup;

    /**
     * 관리자 화면에 표시할 alias 원문입니다.
     */
    @Column(name = "raw_keyword", nullable = false, length = 100)
    private String rawKeyword;

    /**
     * 조회와 전역 중복 방지에 사용하는 정규화된 alias 값입니다.
     */
    @Column(name = "normalized_keyword", nullable = false, unique = true, length = 100)
    private String normalizedKeyword;

    /**
     * alias 연결이 생성된 출처입니다.
     *
     * <p>관리자 수동 등록, AI 추천 승인, 추후 시스템 규칙 기반 등록을
     * 구분하기 위해 사용합니다.</p>
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "source_type", nullable = false, length = 30)
    private KeywordAliasSourceType sourceType;

    /**
     * 비활성 alias는 운영 이력 보존을 위해 남겨두지만 캐시와 집계에서는 제외합니다.
     */
    @Column(nullable = false)
    private Boolean active;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
