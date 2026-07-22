package com.example.backendspring.controller.admin;

import com.example.backendspring.dto.CrawlerKeywordRequest;
import com.example.backendspring.dto.CrawlerKeywordResponse;
import com.example.backendspring.service.CrawlerKeywordService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

/**
 * 최소 관리자 페이지용 키워드 관리 API입니다.
 * 현재 단계에서는 목록 조회, 등록, 활성/비활성 전환만 제공합니다.
 */
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/admin/keywords")
public class AdminKeywordController {

    private final CrawlerKeywordService crawlerKeywordService;

    /**
     * 관리자 페이지에서 운영 키워드 목록을 조회합니다.
     */
    @GetMapping
    public ResponseEntity<List<CrawlerKeywordResponse>> getKeywords() {
        return ResponseEntity.ok(crawlerKeywordService.getKeywords());
    }

    /**
     * 관리자 페이지에서 새 운영 키워드를 추가합니다.
     */
    @PostMapping
    public ResponseEntity<CrawlerKeywordResponse> createKeyword(
            @Valid @RequestBody CrawlerKeywordRequest request
    ) {
        try {
            return ResponseEntity.ok(crawlerKeywordService.createKeyword(request));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * 삭제 대신 활성/비활성 전환만 제공합니다.
     * MVP 단계에서는 데이터 유실 가능성이 있는 삭제 기능을 의도적으로 제외합니다.
     */
    @PatchMapping("/{id}/toggle")
    public ResponseEntity<CrawlerKeywordResponse> toggleKeyword(@PathVariable Long id) {
        try {
            return ResponseEntity.ok(crawlerKeywordService.toggleKeyword(id));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
        }
    }
}
