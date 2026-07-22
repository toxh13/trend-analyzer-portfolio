package com.example.backendspring.controller;

import com.example.backendspring.config.WebConfig;
import com.example.backendspring.config.security.OAuth2LoginSuccessHandler;
import com.example.backendspring.config.security.SecurityConfig;
import com.example.backendspring.controller.admin.AdminCrawlBatchRunController;
import com.example.backendspring.service.CrawlBatchRunService;
import com.example.backendspring.service.CustomOAuth2UserService;
import com.example.backendspring.service.CustomOidcUserService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.data.jpa.mapping.JpaMetamodelMappingContext;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.security.test.context.support.WithMockUser;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest({CrawlBatchRunController.class, AdminCrawlBatchRunController.class})
@Import({WebConfig.class, SecurityConfig.class})
@TestPropertySource(properties = {
        "app.security.crawler-api-key=test-crawler-key",
        "CORS_ALLOWED_ORIGINS=http://localhost:3000"
})
class CrawlBatchRunSecurityPathTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CrawlBatchRunService crawlBatchRunService;

    @MockBean
    private CustomOAuth2UserService customOAuth2UserService;

    @MockBean
    private CustomOidcUserService customOidcUserService;

    @MockBean
    private OAuth2LoginSuccessHandler oauth2LoginSuccessHandler;

    @MockBean(name = "jpaMappingContext")
    private JpaMetamodelMappingContext jpaMetamodelMappingContext;

    @Test
    void completedPathRequiresExistingCrawlerApiKey() throws Exception {
        mockMvc.perform(post("/api/v1/crawling/runs/completed")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(CrawlBatchRunControllerTest.validJson()))
                .andExpect(status().isForbidden());
    }

    @Test
    void startPathRequiresExistingCrawlerApiKey() throws Exception {
        mockMvc.perform(post("/api/v1/crawling/runs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"runId":"11111111-1111-4111-8111-111111111111","startedAt":"2026-07-20T00:00:00Z"}
                                """))
                .andExpect(status().isForbidden());
    }

    @Test
    void startPathAllowsValidApiKeyWithoutSessionOrCsrfToken() throws Exception {
        mockMvc.perform(post("/api/v1/crawling/runs")
                        .header("X-API-KEY", "test-crawler-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"runId":"11111111-1111-4111-8111-111111111111","startedAt":"2026-07-20T00:00:00Z"}
                                """))
                .andExpect(status().isOk());
    }

    @Test
    void completedPathAllowsValidApiKeyWithoutSessionOrCsrfToken() throws Exception {
        mockMvc.perform(post("/api/v1/crawling/runs/completed")
                        .header("X-API-KEY", "test-crawler-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(CrawlBatchRunControllerTest.validJson()))
                .andExpect(status().isOk());
    }

    @Test
    @WithMockUser(roles = "USER")
    void adminRunHistoryRejectsNonAdminUser() throws Exception {
        mockMvc.perform(get("/api/v1/admin/crawling/runs"))
                .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    void adminRunHistoryAllowsAdminUser() throws Exception {
        mockMvc.perform(get("/api/v1/admin/crawling/runs"))
                .andExpect(status().isOk());
    }
}
