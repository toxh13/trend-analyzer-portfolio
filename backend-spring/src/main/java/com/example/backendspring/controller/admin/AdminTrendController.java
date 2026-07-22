package com.example.backendspring.controller.admin;

import com.example.backendspring.service.TrendAnalysticService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 관리자 전용 트렌드 분석 컨트롤러입니다.
 * 공개 트렌드 조회 API와 운영성 수동 실행 API를 분리하여 보안 범위를 명확히 합니다.
 */
@RestController
@RequiredArgsConstructor
@Slf4j
@RequestMapping("/api/v1/admin/trends")
public class AdminTrendController {

    private final TrendAnalysticService trendAnalysticService;

    /**
     * 관리자가 즉시 트렌드 분석 배치를 실행합니다.
     * /api/v1/admin/** 경로는 SecurityConfig에서 ROLE_ADMIN만 접근할 수 있도록 보호됩니다.
     */
    @PostMapping("/analyze-now")
    public ResponseEntity<String> analyzeNow() {
        log.info("관리자 수동 트렌드 분석 실행 요청");
        trendAnalysticService.analyzeAndUpdateTrends();
        return ResponseEntity.ok("분석 완료");
    }
}
