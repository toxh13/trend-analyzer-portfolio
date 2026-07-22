package com.example.backendspring.controller;

import com.example.backendspring.dto.CategoryResponseDto;
import com.example.backendspring.service.CategoryService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * CategoryController - React 대시보드에서 사용할 동적 카테고리 목록 API를 제공합니다.
 */
@RestController
@RequiredArgsConstructor
@Slf4j
@RequestMapping("/api/v1/trends/categories")
public class CategoryController {
    private final CategoryService categoryService;

    /**
     * DB에 저장된 카테고리 목록을 조회합니다.
     */
    @GetMapping
    public ResponseEntity<List<CategoryResponseDto>> getCategories() {
        log.info("트렌드 카테고리 목록 조회");
        List<CategoryResponseDto> dtoList = categoryService.getAvailableCategories();
        return ResponseEntity.ok(dtoList);
    }
}
