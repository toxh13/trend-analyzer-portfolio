package com.example.backendspring.dto;

import com.fasterxml.jackson.annotation.JsonCreator;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.Map;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class ExtractedKeywordDto {
    private String keyword;
    private int occurrenceCount;

    /**
     * 배포 전환 중에는 기존 문자열 배열과 새 객체 배열을 모두 받을 수 있게 합니다.
     */
    @JsonCreator(mode = JsonCreator.Mode.DELEGATING)
    public ExtractedKeywordDto(Object value) {
        if (value instanceof String stringValue) {
            this.keyword = stringValue;
            this.occurrenceCount = 1;
            return;
        }

        if (value instanceof Map<?, ?> mapValue) {
            Object keywordValue = mapValue.get("keyword");
            Object countValue = mapValue.get("occurrenceCount");
            this.keyword = keywordValue == null ? null : String.valueOf(keywordValue);
            this.occurrenceCount = countValue instanceof Number number ? number.intValue() : 1;
            return;
        }

        throw new IllegalArgumentException("키워드는 문자열 또는 keyword/occurrenceCount 객체여야 합니다.");
    }
}
