package com.example.backendspring.controller;

import com.example.backendspring.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.web.csrf.CsrfToken;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AuthControllerTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private CsrfToken csrfToken;

    @InjectMocks
    private AuthController authController;

    @Test
    @DisplayName("CSRF 토큰 엔드포인트는 토큰과 헤더명을 반환한다")
    void getCsrfTokenReturnsTokenAndHeaderName() {
        when(csrfToken.getToken()).thenReturn("csrf-token-value");
        when(csrfToken.getHeaderName()).thenReturn("X-XSRF-TOKEN");

        Map<String, String> response = authController.getCsrfToken(csrfToken).getBody();

        assertThat(response).isNotNull();
        assertThat(response).containsEntry("token", "csrf-token-value");
        assertThat(response).containsEntry("headerName", "X-XSRF-TOKEN");
    }
}
