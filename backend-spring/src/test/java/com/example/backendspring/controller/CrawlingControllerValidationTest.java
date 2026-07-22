package com.example.backendspring.controller;

import com.example.backendspring.service.CrawlingService;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class CrawlingControllerValidationTest {

    @Test
    void rejectsMissingPublishedAtWithBadRequest() throws Exception {
        CrawlingService crawlingService = mock(CrawlingService.class);
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new CrawlingController(crawlingService))
                .build();

        mockMvc.perform(post("/api/v1/crawling")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "title": "기사 제목",
                                  "summary": "기사 요약",
                                  "sourceUrl": "https://example.com/article",
                                  "source": "테스트 언론사",
                                  "category": "IT/과학",
                                  "keywords": []
                                }
                                """))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(crawlingService);
    }
}
