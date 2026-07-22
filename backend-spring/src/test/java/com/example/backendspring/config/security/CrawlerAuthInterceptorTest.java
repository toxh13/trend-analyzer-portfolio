package com.example.backendspring.config.security;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;

class CrawlerAuthInterceptorTest {

    @Test
    @DisplayName("API 키가 없거나 다르면 크롤링 요청을 403으로 차단한다")
    void rejectsMissingOrInvalidApiKey() throws Exception {
        CrawlerAuthInterceptor interceptor = new CrawlerAuthInterceptor("server-secret");

        MockHttpServletResponse missingResponse = new MockHttpServletResponse();
        assertThat(interceptor.preHandle(new MockHttpServletRequest(), missingResponse, new Object())).isFalse();
        assertThat(missingResponse.getStatus()).isEqualTo(HttpStatus.FORBIDDEN.value());

        MockHttpServletRequest invalidRequest = new MockHttpServletRequest();
        invalidRequest.addHeader("X-API-KEY", "wrong-secret");
        MockHttpServletResponse invalidResponse = new MockHttpServletResponse();
        assertThat(interceptor.preHandle(invalidRequest, invalidResponse, new Object())).isFalse();
        assertThat(invalidResponse.getStatus()).isEqualTo(HttpStatus.FORBIDDEN.value());
    }

    @Test
    @DisplayName("API 키가 정확히 일치할 때만 크롤링 요청을 통과시킨다")
    void acceptsMatchingApiKey() throws Exception {
        CrawlerAuthInterceptor interceptor = new CrawlerAuthInterceptor("server-secret");
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-API-KEY", "server-secret");

        assertThat(interceptor.preHandle(request, new MockHttpServletResponse(), new Object())).isTrue();
    }

    @Test
    @DisplayName("서버 API 키 자체가 null 또는 공백이면 애플리케이션 설정 오류로 즉시 실패한다")
    void rejectsBlankServerSecretAtConstruction() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new CrawlerAuthInterceptor(null))
                .withMessage("crawler API key must not be blank");
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new CrawlerAuthInterceptor("   "))
                .withMessage("crawler API key must not be blank");
    }
}
