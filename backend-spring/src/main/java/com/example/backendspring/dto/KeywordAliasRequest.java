package com.example.backendspring.dto;

/**
 * 대표 키워드 그룹에 alias를 추가할 때 사용하는 요청 DTO입니다.
 *
 * <p>입력값은 화면 표시용 원문으로 보존하고, 서비스 계층에서 중복 검사와
 * 캐시 조회에 사용할 정규화 값을 별도로 생성합니다.</p>
 */
public record KeywordAliasRequest(
        String rawKeyword
) {
}
