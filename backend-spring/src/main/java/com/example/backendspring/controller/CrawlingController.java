package com.example.backendspring.controller;

import com.example.backendspring.dto.CrawlingRequestDto;
import com.example.backendspring.service.CrawlingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1")
@Slf4j
public class CrawlingController {
    // CrawlingService를 통해 파이썬으로부터 전달받은 크롤링 데이터를 저장하는 역할을 수행합니다.
    // 생성자 주입(@RequiredArgsConstructor)을 통해 주입됩니다.

    private final CrawlingService crawlingService;

    /**
     * 크롤링 데이터 수신 엔드포인트
     *
     * 요청 예: POST /api/v1/crawling
     * 요청 바디: CrawlingRequestDto (JSON)
     *
     * @param crawlDto 파이썬에서 전달된 크롤링 데이터 DTO
     * @return 데이터 적재 성공/실패 메시지를 담은 ResponseEntity
     */
    @PostMapping("/crawling")
    public ResponseEntity<String> receiveCrawledData(@Valid @RequestBody CrawlingRequestDto crawlDto){
        // 전달된 DTO의 타이틀을 로그로 남겨 디버깅에 활용합니다.
        log.info("파이썬에서 데이터받아옮: {}", crawlDto.getTitle());

        try{
            // 서비스 레이어에 저장 책임을 위임합니다.
            crawlingService.saveCrawledData(crawlDto);
            // 정상 처리 시 HTTP 200과 메시지를 반환합니다.
            return ResponseEntity.ok("데이터 적재 완료");
        } catch (Exception e) {
            // 예외 발생 시 스택트레이스를 로그에 남기고 500을 반환합니다.
            log.error("데이터 적재 중 오류 발생: ", e);
            return ResponseEntity.internalServerError().body("서버 오류로 데이터 적재 실패");
        }
    }

}
