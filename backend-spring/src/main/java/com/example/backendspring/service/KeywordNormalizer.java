package com.example.backendspring.service;

import org.springframework.stereotype.Component;

import java.util.Locale;

/**
 * 키워드 비교/중복 체크에 사용하는 공통 정규화 컴포넌트입니다.
 *
 * 주의:
 * - 화면 표시용 키워드는 원본을 유지합니다.
 * - 비교/중복 체크/캐시 조회에는 normalize 결과를 사용합니다.
 *
 * 예:
 * " 생성형 AI " -> "생성형ai"
 * "A.I." -> "ai"
 * "Artificial Intelligence" -> "artificialintelligence"
 */
@Component
public class KeywordNormalizer {

    public String normalize(String keyword) {
        if (keyword == null) {
            return "";
        }

        return keyword
                .trim()
                .toLowerCase(Locale.ROOT)
                // 모든 공백 제거: "생성형 AI"와 "생성형AI"를 같은 값으로 보기 위함
                .replaceAll("\\s+", "")
                // 짧은 약어 비교 보정: "A.I."와 "AI" 차이를 줄임
                .replace(".", "")
                // 하이픈 표현 차이 보정: "generative-ai"와 "generative ai" 차이 완화
                .replace("-", "");
    }

    public String trimToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }

        return value.trim();
    }
}