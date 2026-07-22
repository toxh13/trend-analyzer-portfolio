package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 관리자가 직접 관리하는 대표 키워드 그룹 엔티티입니다.
 *
 * <p>승인된 alias가 있으면 트렌드 화면에서는 이 대표 키워드 기준으로
 * 합산된 결과를 보여줍니다. 예를 들어 "AI"와 "Artificial Intelligence"를
 * 하나의 대표 키워드로 묶을 수 있습니다.</p>
 */
@Entity
@Table(name = "keyword_groups")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class KeywordGroup {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "keyword_group_seq")
    @SequenceGenerator(
            name = "keyword_group_seq",
            sequenceName = "KEYWORD_GROUP_SEQ",
            allocationSize = 1
    )
    private Long id;

    /**
     * 대시보드와 관리자 화면에 표시되는 대표 키워드입니다.
     */
    @Column(name = "canonical_keyword", nullable = false, length = 100)
    private String canonicalKeyword;

    /**
     * 대표 키워드의 중복 여부를 판단할 때 사용하는 정규화 값입니다.
     *
     * <p>띄어쓰기나 대소문자 차이 때문에 같은 의미의 그룹이 중복 생성되지
     * 않도록 표시값과 별도로 저장합니다.</p>
     */
    @Column(name = "normalized_canonical_keyword", nullable = false, unique = true, length = 100)
    private String normalizedCanonicalKeyword;

    /**
     * 관리자가 그룹의 목적을 이해하기 위한 설명입니다.
     */
    @Column(length = 500)
    private String description;

    /**
     * 비활성화된 그룹은 alias 기반 트렌드 병합 대상에서 제외합니다.
     */
    @Column(nullable = false)
    private Boolean active;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
