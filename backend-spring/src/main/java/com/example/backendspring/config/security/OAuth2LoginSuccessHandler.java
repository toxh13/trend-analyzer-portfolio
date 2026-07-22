package com.example.backendspring.config.security;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.security.web.authentication.SimpleUrlAuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
@Slf4j
public class OAuth2LoginSuccessHandler extends SimpleUrlAuthenticationSuccessHandler {

    @Value("${app.oauth2.success-redirect-uri:http://localhost:3000}")
    private String successRedirectUri;

    /**
     * 소셜 로그인 성공 후 프론트엔드 대시보드로 돌려보냅니다.
     * 운영에서는 FRONTEND_BASE_URL 또는 app.oauth2.success-redirect-uri 값을 배포 도메인으로 지정합니다.
     */
    @Override
    public void onAuthenticationSuccess(
            HttpServletRequest request,
            HttpServletResponse response,
            Authentication authentication
    ) throws IOException, ServletException {
        log.info(
                "OAuth2 로그인 성공 처리: authenticationClass={}, principalClass={}, redirectUri={}",
                authentication != null ? authentication.getClass().getName() : null,
                authentication != null && authentication.getPrincipal() != null
                        ? authentication.getPrincipal().getClass().getName()
                        : null,
                successRedirectUri
        );

        clearAuthenticationAttributes(request);
        getRedirectStrategy().sendRedirect(request, response, successRedirectUri);
    }
}
