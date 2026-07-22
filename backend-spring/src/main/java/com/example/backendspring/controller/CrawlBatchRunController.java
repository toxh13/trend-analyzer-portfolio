package com.example.backendspring.controller;

import com.example.backendspring.dto.CrawlBatchRunCompleteRequest;
import com.example.backendspring.dto.CrawlBatchRunResponse;
import com.example.backendspring.dto.CrawlBatchRunStartRequest;
import com.example.backendspring.service.CrawlBatchRunService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/crawling/runs")
public class CrawlBatchRunController {

    private final CrawlBatchRunService crawlBatchRunService;

    @PostMapping
    public ResponseEntity<CrawlBatchRunResponse> start(
            @Valid @RequestBody CrawlBatchRunStartRequest request
    ) {
        return ResponseEntity.ok(crawlBatchRunService.start(request));
    }

    @PostMapping("/completed")
    public ResponseEntity<CrawlBatchRunResponse> complete(
            @Valid @RequestBody CrawlBatchRunCompleteRequest request
    ) {
        return ResponseEntity.ok(crawlBatchRunService.complete(request));
    }
}
