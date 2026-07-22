package com.example.backendspring.entity;

/**
 * alias가 어떤 경로로 등록되었는지 구분합니다.
 * ADMIN: 관리자가 직접 추가
 * AI_APPROVED: AI 추천을 관리자가 승인
 * SYSTEM: 초기 데이터 또는 시스템 기본값
 */
public enum KeywordAliasSourceType {
    ADMIN,
    AI_APPROVED,
    SYSTEM
}