package com.example.backendspring.entity;

/**
 * 관리자 키워드의 운영 용도를 구분하는 타입입니다.
 *
 * TRACKING: 추적하고 싶은 주요 키워드
 * BLOCKED : 의미 없는 키워드로 저장/집계에서 제외할 키워드
 */
public enum CrawlerKeywordType {
    TRACKING,
    BLOCKED
}