package com.example.backendspring.dto;

/**
 * 대표 키워드 그룹을 생성하거나 수정할 때 사용하는 요청 DTO입니다.
 *
 * <p>대표 키워드 그룹은 트렌드 화면에 표시될 기준 키워드를 의미합니다.
 * 예를 들어 "AI", "Artificial Intelligence" 같은 alias를 하나의 대표
 * 키워드 그룹에 연결하면 화면에서는 하나의 키워드로 합산해서 보여줄 수 있습니다.</p>
 */
public record KeywordGroupRequest(
        String canonicalKeyword,
        String description,
        Boolean active
) {
}
