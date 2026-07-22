package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class TrendHistoryEvidenceResponseDto {
    private String date;
    private String timezone;
    private String firstCanonicalKeyword;
    private String secondCanonicalKeyword;
    private List<ArticleEvidenceDto> firstArticles;
    private List<ArticleEvidenceDto> secondArticles;
}
