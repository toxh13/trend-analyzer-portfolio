package com.example.backendspring.dto;


import com.example.backendspring.entity.KeywordAlias;
import com.example.backendspring.entity.KeywordAliasSourceType;

import java.time.LocalDateTime;

/**
 * 관리자 화면에 보여줄 alias 응답 DTO입니다.
 */
public record KeywordAliasResponse(
        Long id,
        String rawKeyword,
        String normalizedKeyword,
        KeywordAliasSourceType sourceType,
        Boolean active,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {

    public static KeywordAliasResponse from(KeywordAlias alias) {
        return new KeywordAliasResponse(
                alias.getId(),
                alias.getRawKeyword(),
                alias.getNormalizedKeyword(),
                alias.getSourceType(),
                alias.getActive(),
                alias.getCreatedAt(),
                alias.getUpdatedAt()
        );
    }
}