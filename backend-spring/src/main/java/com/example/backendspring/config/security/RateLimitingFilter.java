package com.example.backendspring.config.security;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Slf4j
public class RateLimitingFilter implements Filter {

    // [최적화] 스레드 경합 상황에서 동시성 데드락을 방지하고 고속 조회가 가능한 ConcurrentHashMap 채택
    private final Map<String, SimpleTokenBucket> ipBucketMap = new ConcurrentHashMap<>();

    // [개발/운영 분리] 로컬 개발 중 관리자 화면 새로고침으로 429가 쉽게 발생하지 않도록 기본값을 완화합니다.
    @Value("${app.security.rate-limit.capacity:120}")
    private long rateLimitCapacity;

    @Value("${app.security.rate-limit.refill-interval-minutes:1}")
    private long rateLimitRefillIntervalMinutes;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String requestUri = httpRequest.getRequestURI();
        String clientIp = httpRequest.getRemoteAddr();

        // OAuth2, 인증 상태 확인, 관리자/내정보 화면의 기본 조회 API는 개발 중 반복 호출이 많으므로 rate limit에서 제외합니다.
        // 실제 운영에서는 app.security.rate-limit.* 값을 조정하거나 Nginx/API Gateway 단에서 별도 제한을 거는 것을 권장합니다.
        if (isExcludedPath(requestUri)) {
            chain.doFilter(request, response);
            return;
        }

        // [변경] 30분 30회 고정값 대신 환경변수 기반 토큰 버킷을 사용합니다.
        SimpleTokenBucket bucket = ipBucketMap.computeIfAbsent(
                clientIp,
                k -> new SimpleTokenBucket(rateLimitCapacity, rateLimitRefillIntervalMinutes)
        );

        if (!bucket.tryConsume()) {
            log.warn("🚨 [트래픽 폭주 차단] 비정상 연사 감지 차단 - IP: {}, URI: {}", clientIp, requestUri);

            httpResponse.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            httpResponse.setContentType("application/json;charset=UTF-8");
            httpResponse.getWriter().write("{\"error\": \"Too Many Requests\", \"message\": \"Rate limit exceeded. Prevent flooding.\"}");
            return;
        }

        chain.doFilter(request, response);
    }

    private boolean isExcludedPath(String requestUri) {
        return requestUri.startsWith("/actuator")
                || requestUri.contains(".ico")
                || requestUri.startsWith("/static")
                || requestUri.startsWith("/oauth2")
                || requestUri.startsWith("/login/oauth2")
                || requestUri.startsWith("/api/v1/auth")
                || requestUri.startsWith("/api/v1/me")
                || requestUri.startsWith("/api/v1/admin")
                || requestUri.startsWith("/api/v1/trends/stats");
    }

    /**
     * [최적화 내부 클래스] 인메모리 초경량 토큰 버킷 알고리즘 엔진
     */
    private static class SimpleTokenBucket {
        private final long capacity;
        private final double refillRatePerSecond;
        private double tokens;
        private long lastRefillTimestamp;

        public SimpleTokenBucket(long capacity, long refillIntervalMinutes) {
            this.capacity = Math.max(capacity, 1);
            long safeRefillIntervalMinutes = Math.max(refillIntervalMinutes, 1);
            this.refillRatePerSecond = (double) this.capacity / (safeRefillIntervalMinutes * 60);
            this.tokens = this.capacity;
            this.lastRefillTimestamp = System.currentTimeMillis();
        }

        public synchronized boolean tryConsume() {
            refill();
            if (tokens >= 1.0) {
                tokens -= 1.0;
                return true;
            }
            return false;
        }

        private void refill() {
            long now = System.currentTimeMillis();
            double elapsedSeconds = (double) (now - lastRefillTimestamp) / 1000.0;

            tokens = Math.min(capacity, tokens + (elapsedSeconds * refillRatePerSecond));
            lastRefillTimestamp = now;
        }
    }
}
