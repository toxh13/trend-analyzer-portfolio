package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@Table(name = "subscriptions")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class Subscription {

    // Article.java, ArticleKeyword.java 등 변경
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "sub_seq")
    @SequenceGenerator(name = "sub_seq", sequenceName = "SUB_SEQ", allocationSize = 1)
    private Long id;

    // [최적화/보안] 다대일(N:1) 관계 매핑.
    // FetchType.LAZY(지연 로딩) 설정은 필수입니다. EAGER(즉시 로딩) 사용 시 구독 목록을 조회할 때마다
    // 무조건 User 데이터까지 조인(Join)하여 가져오게 되므로 대규모 트래픽에서 N+1 성능 병목을 유발합니다.
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "keyword", nullable = false)
    private String keyword; // 예: "클라우드", "LLM" 등 사용자가 구독한 트렌드 단어

    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;
}