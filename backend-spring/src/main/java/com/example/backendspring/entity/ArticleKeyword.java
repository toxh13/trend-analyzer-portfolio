package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "article_keywords")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ArticleKeyword {

    // Article.java, ArticleKeyword.java 등 변경
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "keyword_seq")
    @SequenceGenerator(name = "keyword_seq", sequenceName = "KEYWORD_SEQ", allocationSize = 1)
    private Long id;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "article_id", nullable = false)
    private Article article;

    @Column(nullable = false)
    private String keyword;


    @Column(nullable = false)
    private int weight;

    private LocalDateTime createdAt;


}
