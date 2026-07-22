package com.example.backendspring.config;

import com.example.backendspring.config.security.CrawlerAuthInterceptor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    // [보안/최적화] 콤마(,)로 구분된 단일 문자열로 환경변수를 받은 후 내부적으로 안전하게 배열 분리 처리
    // 이유: 클라우드 인프라(OCI, Kubernetes 등) 컨테이너 주입 시 배열 형태보다 단일 문자열 포맷이 설정 관리상 훨씬 안정적임.
    @Value("${CORS_ALLOWED_ORIGINS:http://localhost:3000,http://localhost:5173,http://shdomain.kro.kr:3000}")
    private String allowedOriginsRaw;

    @Value("${app.security.crawler-api-key:local-fallback-secret-key-1234!}")
    private String crawlerApiKey;

    /**
     * [보안 강화 주석] 프로덕션 레벨 엄격한 CORS 화이트리스트 바인딩
     * - 대상: 브라우저 SOP 정책 우회 제어
     * - 이유: allowCredentials(true) 환경에서 와일드카드(*)를 사용하거나 도메인을 검증하지 않으면
     * 악성 스크립트 사이트에서 본 시스템 API로 CSRF(교차 사이트 요청 위조) 공격을 감행할 수 있음.
     * 따라서 인입된 원본 문자열의 트림(Trim) 처리를 거쳐 정확히 허용된 도메인만 화이트리스트로 메모리에 로드함.
     */
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        // 쉼표 기준 스트링 분리 및 각 도메인의 앞뒤 공백 제거 최적화 연산
        String[] strictOrigins = Arrays.stream(allowedOriginsRaw.split(","))
                .map(String::trim)
                .toArray(String[]::new);

        registry.addMapping("/**")
                .allowedOrigins(strictOrigins) // 정제된 안전 화이트리스트 배열 바인딩
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600); // [최적화] 브라우저가 Preflight(OPTIONS) 요청을 1시간 동안 캐싱하게 하여 불필요한 핸드셰이크 트래픽 비용 절감
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new CrawlerAuthInterceptor(crawlerApiKey))
                .addPathPatterns(
                        "/api/v1/crawling",
                        "/api/v1/crawling/runs",
                        "/api/v1/crawling/runs/completed"
                );
    }


    /*
     * 💡 [추가 보완 필요 주석]
     * 현재 CORS 설정 구조는 WebMvcConfigurer 인터페이스 기반의 단순 서블릿 매핑 기법을 사용 중임.
     * 추후 스프링 시큐리티(Spring Security) 코어 프레임워크가 프로젝트에 의존성으로 추가되는 시점에는
     * 시큐리티 필터 체인(Security Filter Chain) 내의 CorsConfigurationSource 컴포넌트 내부로
     * 해당 allowedOrigins 주입 로직을 이관해야 필터 레이어 단에서의 인가 거부 에러를 방지할 수 있음.
     */
}
