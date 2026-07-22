package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ArticleResponseDto {
    private String id;       // 기사 고유 ID
    private String title;    // 기사 제목
    private String source;   // 언론사 (전자신문 등)
    private String date;     // 발행일 (예: "2026. 06. 21")
    private String url;      // 원본 링크
}
