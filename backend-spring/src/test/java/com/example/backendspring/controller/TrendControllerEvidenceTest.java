package com.example.backendspring.controller;

import com.example.backendspring.dto.TrendHistoryEvidenceResponseDto;
import com.example.backendspring.service.TrendService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.LocalDate;
import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class TrendControllerEvidenceTest {

    @Test
    @DisplayName("기사 근거 API는 limit 기본값 5와 ISO 날짜를 서비스에 전달한다")
    void getHistoryEvidenceUsesDefaultLimit() throws Exception {
        TrendService trendService = mock(TrendService.class);
        TrendController controller = new TrendController(trendService);
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(controller).build();
        LocalDate date = LocalDate.of(2026, 7, 19);
        TrendHistoryEvidenceResponseDto response = TrendHistoryEvidenceResponseDto.builder()
                .date(date.toString())
                .timezone("Asia/Seoul")
                .firstCanonicalKeyword("인공지능")
                .secondCanonicalKeyword("반도체")
                .firstArticles(List.of())
                .secondArticles(List.of())
                .build();
        when(trendService.getKeywordHistoryEvidence("AI", "반도체", date, 5)).thenReturn(response);

        mockMvc.perform(get("/api/v1/trends/history/evidence")
                        .param("firstKeyword", "AI")
                        .param("secondKeyword", "반도체")
                        .param("date", "2026-07-19"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.date").value("2026-07-19"))
                .andExpect(jsonPath("$.timezone").value("Asia/Seoul"))
                .andExpect(jsonPath("$.firstArticles").isArray())
                .andExpect(jsonPath("$.secondArticles").isArray());

        verify(trendService).getKeywordHistoryEvidence("AI", "반도체", date, 5);
    }

    @Test
    @DisplayName("기사 근거 API의 날짜 형식이 잘못되면 400 오류를 반환한다")
    void getHistoryEvidenceRejectsMalformedDate() throws Exception {
        TrendController controller = new TrendController(mock(TrendService.class));
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(controller).build();

        mockMvc.perform(get("/api/v1/trends/history/evidence")
                        .param("firstKeyword", "AI")
                        .param("secondKeyword", "반도체")
                        .param("date", "2026/07/19"))
                .andExpect(status().isBadRequest());
    }
}
