package com.example.backendspring.config.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

@Slf4j
public class CrawlerAuthInterceptor implements HandlerInterceptor {

    private final String serverSecretKey;

    public CrawlerAuthInterceptor(String serverSecretKey) {
        if (!StringUtils.hasText(serverSecretKey)) {
            throw new IllegalArgumentException("crawler API key must not be blank");
        }
        this.serverSecretKey = serverSecretKey;
    }

    /**
     * [보안 최적화 주석] 컨트롤러 진입 전 API KEY 유효성 검증 가드
     * - 대상: POST /api/v1/crawling 엔드포인트
     * - 이유: 유효하지 않은 비인가 요청이 무차별적으로 인입될 경우 비즈니스 로직(Service) 및
     * 데이터베이스 커넥션(I/O)까지 트래픽이 전파되어 시스템 자원이 고갈되는 문제를 서블릿 컨테이너 초입에서 원천 차단함.
     */
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String incomingApiKey = request.getHeader("X-API-KEY");

        // 1. 헤더가 누락되었거나 서버에 지정된 비밀키와 일치하지 않을 경우 즉시 요청 반려
        if (!serverSecretKey.equals(incomingApiKey)) {
            log.warn("🚨 [보안 위협 클리핑] 비인가 유저의 API 접근 차단됨 IP: {}, URI: {}",
                    request.getRemoteAddr(), request.getRequestURI());

            // 컨트롤러까지 자원이 낭비되지 않도록 HTTP Status 403(Forbidden) 응답 반환 후 스레드 종료
            response.sendError(HttpStatus.FORBIDDEN.value(), "Access Denied: Invalid Security API Key.");
            return false;
        }

        // 2. 일치할 경우 무정지 통과
        return true;
    }
}
