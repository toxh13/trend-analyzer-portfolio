package com.example.backendspring.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ExtractedKeywordDtoTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void acceptsLegacyStringAndNewObjectPayloads() throws Exception {
        ExtractedKeywordDto legacy = objectMapper.readValue("\"인공지능\"", ExtractedKeywordDto.class);
        ExtractedKeywordDto current = objectMapper.readValue(
                "{\"keyword\":\"반도체\",\"occurrenceCount\":5}",
                ExtractedKeywordDto.class
        );

        assertThat(legacy.getKeyword()).isEqualTo("인공지능");
        assertThat(legacy.getOccurrenceCount()).isEqualTo(1);
        assertThat(current.getKeyword()).isEqualTo("반도체");
        assertThat(current.getOccurrenceCount()).isEqualTo(5);
    }
}
