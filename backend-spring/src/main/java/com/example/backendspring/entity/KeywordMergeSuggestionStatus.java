package com.example.backendspring.entity;

/**
 * AI 병합 추천 후보의 검토 상태입니다.
 * PENDING: 아직 관리자가 검토하지 않음
 * APPROVED: 관리자가 승인하여 keyword_aliases에 반영됨
 * REJECTED: 관리자가 거절했으며 재추천 대상에서 제외
 */
public enum KeywordMergeSuggestionStatus {
    PENDING,
    APPROVED,
    REJECTED
}