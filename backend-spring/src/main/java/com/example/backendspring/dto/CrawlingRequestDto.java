package com.example.backendspring.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.List;

@Getter @Setter
@NoArgsConstructor
@AllArgsConstructor

public class CrawlingRequestDto {
    @NotBlank(message = "기사 제목은 필수입니다.")
    @Size(max = 1000, message = "기사 제목은 1000자 이하여야 합니다.")
    private String title;
    @NotBlank(message = "기사 요약은 필수입니다.")
    private String summary;
    @NotBlank(message = "기사 URL은 필수입니다.")
    @Size(max = 1000, message = "기사 URL은 1000자 이하여야 합니다.")
    private String sourceUrl;
    @NotBlank(message = "기사 출처는 필수입니다.")
    @Size(max = 255, message = "기사 출처는 255자 이하여야 합니다.")
    private String source;
    @NotBlank(message = "기사 카테고리는 필수입니다.")
    @Size(max = 255, message = "기사 카테고리는 255자 이하여야 합니다.")
    private String category;
    @NotNull(message = "기사 발행 시각은 필수입니다.")
    private LocalDateTime publishedAt;

    private List<ExtractedKeywordDto> keywords;

}
