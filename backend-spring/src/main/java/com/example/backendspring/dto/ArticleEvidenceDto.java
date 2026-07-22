package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;

import java.time.OffsetDateTime;

@Getter
@Builder
public class ArticleEvidenceDto {
    private Long id;
    private String title;
    private String summary;
    private String source;
    private OffsetDateTime publishedAt;
    private String sourceUrl;
}
