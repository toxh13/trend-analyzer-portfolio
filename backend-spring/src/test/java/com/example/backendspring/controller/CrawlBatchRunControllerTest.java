package com.example.backendspring.controller;

import com.example.backendspring.controller.admin.AdminCrawlBatchRunController;
import com.example.backendspring.service.CrawlBatchRunService;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.NOT_FOUND;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class CrawlBatchRunControllerTest {

    @Test
    void rejectsNegativeCountsBeforeCallingService() throws Exception {
        CrawlBatchRunService service = mock(CrawlBatchRunService.class);
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new CrawlBatchRunController(service)).build();

        mockMvc.perform(post("/api/v1/crawling/runs/completed")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validJson().replace("\"durationMs\":60000", "\"durationMs\":-1")))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(service);
    }

    @Test
    void rejectsMissingCountsBeforeCallingService() throws Exception {
        CrawlBatchRunService service = mock(CrawlBatchRunService.class);
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new CrawlBatchRunController(service)).build();

        mockMvc.perform(post("/api/v1/crawling/runs/completed")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validJson().replace("\"durationMs\":60000,", "")))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(service);
    }

    @Test
    void listUsesDefaultAndExplicitLimit() throws Exception {
        CrawlBatchRunService service = mock(CrawlBatchRunService.class);
        when(service.getRecent(20)).thenReturn(List.of());
        when(service.getRecent(5)).thenReturn(List.of());
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new AdminCrawlBatchRunController(service)).build();

        mockMvc.perform(get("/api/v1/admin/crawling/runs"))
                .andExpect(status().isOk())
                .andExpect(content().json("[]"));
        mockMvc.perform(get("/api/v1/admin/crawling/runs").param("limit", "5"))
                .andExpect(status().isOk());

        verify(service).getRecent(20);
        verify(service).getRecent(5);
    }

    @Test
    void detailMapsMissingRunToNotFound() throws Exception {
        CrawlBatchRunService service = mock(CrawlBatchRunService.class);
        when(service.getByRunId("missing"))
                .thenThrow(new ResponseStatusException(NOT_FOUND, "수집 실행 이력을 찾을 수 없습니다."));
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new AdminCrawlBatchRunController(service)).build();

        mockMvc.perform(get("/api/v1/admin/crawling/runs/missing"))
                .andExpect(status().isNotFound());
    }

    static String validJson() {
        return """
                {
                  "runId":"11111111-1111-4111-8111-111111111111",
                  "startedAt":"2026-07-20T00:00:00Z",
                  "completedAt":"2026-07-20T00:01:00Z",
                  "outcome":"SUCCESS",
                  "crawlerOutputCount":3,
                  "validationRejectedCount":0,
                  "duplicateUrlCount":0,
                  "eligibleCount":3,
                  "selectedCount":3,
                  "droppedByLimitCount":0,
                  "preprocessingFailedCount":0,
                  "backendAcknowledgedCount":3,
                  "httpFailedCount":0,
                  "transportFailedCount":0,
                  "durationMs":60000,
                  "channels":[
                    {"channel":"naver","outcome":"SUCCESS","validatedArticleCount":1,"sourceInvalidCount":0,"successfulUnits":1,"partialUnits":0,"emptyUnits":0,"failedUnits":0},
                    {"channel":"daum","outcome":"SUCCESS","validatedArticleCount":1,"sourceInvalidCount":0,"successfulUnits":1,"partialUnits":0,"emptyUnits":0,"failedUnits":0},
                    {"channel":"rss","outcome":"SUCCESS","validatedArticleCount":1,"sourceInvalidCount":0,"successfulUnits":1,"partialUnits":0,"emptyUnits":0,"failedUnits":0}
                  ]
                }
                """;
    }
}
