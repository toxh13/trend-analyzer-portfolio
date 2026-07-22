package com.example.backendspring.controller.admin;

import com.example.backendspring.dto.CrawlBatchRunResponse;
import com.example.backendspring.service.CrawlBatchRunService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/admin/crawling/runs")
public class AdminCrawlBatchRunController {

    private final CrawlBatchRunService crawlBatchRunService;

    @GetMapping
    public ResponseEntity<List<CrawlBatchRunResponse>> getRecent(
            @RequestParam(defaultValue = "20") int limit
    ) {
        return ResponseEntity.ok(crawlBatchRunService.getRecent(limit));
    }

    @GetMapping("/{runId}")
    public ResponseEntity<CrawlBatchRunResponse> getByRunId(@PathVariable String runId) {
        return ResponseEntity.ok(crawlBatchRunService.getByRunId(runId));
    }
}
