package com.example.backendspring.config.security;

import com.example.backendspring.service.CustomOAuth2UserService;
import com.example.backendspring.service.CustomOidcUserService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.web.DefaultOAuth2AuthorizationRequestResolver;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizationRequestResolver;
import org.springframework.security.oauth2.core.endpoint.OAuth2AuthorizationRequest;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final CustomOAuth2UserService customOAuth2UserService;
    private final CustomOidcUserService customOidcUserService;
    private final OAuth2LoginSuccessHandler oauth2LoginSuccessHandler;

    @Value("${CORS_ALLOWED_ORIGINS:http://localhost:3000,http://localhost:5173}")
    private String allowedOriginsRaw;

    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            ObjectProvider<ClientRegistrationRepository> clientRegistrationRepositoryProvider
    ) throws Exception {
        http
                // 세션 기반 브라우저 요청은 CSRF 토큰을 사용하고, 크롤러 수집 API만 예외로 둡니다.
                .csrf(csrf -> csrf
                        .csrfTokenRepository(cookieCsrfTokenRepository())
                        .ignoringRequestMatchers(
                                "/api/v1/crawling",
                                "/api/v1/crawling/runs",
                                "/api/v1/crawling/runs/completed"
                        )
                )
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .httpBasic(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                // [OAuth2 세션 보존]
                // 로그인 성공 후 SecurityContext가 HttpSession에 저장되어 /api/v1/auth/me에서 같은 사용자를 읽을 수 있도록 명시합니다.
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
                .securityContext(securityContext -> securityContext.requireExplicitSave(false))
                .authorizeHttpRequests(auth -> auth
                        // 관리자 API는 공개 API보다 먼저 선언해 운영성 기능을 ROLE_ADMIN으로 보호합니다.
                        .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                        .requestMatchers("/actuator/metrics", "/actuator/metrics/**").hasRole("ADMIN")
                        .requestMatchers(
                                "/",
                                "/error",
                                "/actuator/health",
                                "/v3/api-docs/**",
                                "/swagger-ui/**",
                                "/swagger-ui.html",
                                "/api/v1/trends/**",
                                "/api/v1/crawling",
                                "/api/v1/crawling/runs",
                                "/api/v1/crawling/runs/completed",
                                "/api/v1/auth/**",
                                "/oauth2/**",
                                "/login/oauth2/**"
                        ).permitAll()
                        // Discord OAuth callback은 Discord가 호출하는 공개 진입점입니다.
                        // 실제 계정 연결은 세션 state와 현재 로그인 사용자를 서비스 계층에서 다시 검증합니다.
                        .requestMatchers("/api/v1/me/discord/callback").permitAll()
                        // 내정보, 구독 키워드, Discord 연동 시작/해제는 로그인 사용자만 접근 가능합니다.
                        .requestMatchers("/api/v1/me/**").authenticated()
                        .anyRequest().authenticated()
                );

        // GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET이 등록된 경우에만 OAuth2 login 필터를 활성화합니다.
        // 등록 정보가 없는 로컬 환경에서도 서버가 죽지 않도록 ObjectProvider로 방어합니다.
        ClientRegistrationRepository clientRegistrationRepository = clientRegistrationRepositoryProvider.getIfAvailable();
        if (clientRegistrationRepository != null) {
            OAuth2AuthorizationRequestResolver authorizationRequestResolver =
                    googleAccountSelectResolver(clientRegistrationRepository);

            http.oauth2Login(oauth2 -> oauth2
                    // Google 로그인 요청에 prompt=select_account를 추가해 재로그인 시 계정 선택 화면을 표시합니다.
                    .authorizationEndpoint(authorization -> authorization
                            .authorizationRequestResolver(authorizationRequestResolver)
                    )
                    .userInfoEndpoint(userInfo -> userInfo
                            // 일반 OAuth2 provider용입니다. Google은 openid scope 때문에 아래 oidcUserService를 탑니다.
                            .userService(customOAuth2UserService)
                            // Google OIDC 로그인용입니다. 여기에서 internalUserId를 principal에 주입합니다.
                            .oidcUserService(customOidcUserService)
                    )
                    .successHandler(oauth2LoginSuccessHandler)
            );
        }

        return http.build();
    }

    @Bean
    public CookieCsrfTokenRepository cookieCsrfTokenRepository() {
        CookieCsrfTokenRepository repository = CookieCsrfTokenRepository.withHttpOnlyFalse();
        repository.setCookiePath("/");
        return repository;
    }

    /**
     * Google OAuth2 로그인 요청에 계정 선택 옵션을 추가합니다.
     *
     * 목적:
     * - 서비스 로그아웃 후 재로그인할 때 기존 Google 계정으로 자동 로그인되는 문제를 방지합니다.
     * - Google 계정 자체를 로그아웃시키지 않고, 로그인 시점에 사용자가 계정을 선택하게 만듭니다.
     */
    private OAuth2AuthorizationRequestResolver googleAccountSelectResolver(
            ClientRegistrationRepository clientRegistrationRepository
    ) {
        DefaultOAuth2AuthorizationRequestResolver defaultResolver =
                new DefaultOAuth2AuthorizationRequestResolver(
                        clientRegistrationRepository,
                        "/oauth2/authorization"
                );

        return new OAuth2AuthorizationRequestResolver() {
            @Override
            public OAuth2AuthorizationRequest resolve(HttpServletRequest request) {
                OAuth2AuthorizationRequest authorizationRequest = defaultResolver.resolve(request);
                return addGoogleAccountSelectPrompt(authorizationRequest);
            }

            @Override
            public OAuth2AuthorizationRequest resolve(
                    HttpServletRequest request,
                    String clientRegistrationId
            ) {
                OAuth2AuthorizationRequest authorizationRequest =
                        defaultResolver.resolve(request, clientRegistrationId);
                return addGoogleAccountSelectPrompt(authorizationRequest);
            }
        };
    }

    /**
     * Google Authorization Server로 전달되는 추가 파라미터를 설정합니다.
     * prompt=select_account를 넣으면 Google 계정 선택 화면이 표시됩니다.
     */
    private OAuth2AuthorizationRequest addGoogleAccountSelectPrompt(
            OAuth2AuthorizationRequest authorizationRequest
    ) {
        if (authorizationRequest == null) {
            return null;
        }

        return OAuth2AuthorizationRequest.from(authorizationRequest)
                .additionalParameters(parameters -> parameters.put("prompt", "select_account"))
                .build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        List<String> allowedOrigins = Arrays.stream(allowedOriginsRaw.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isBlank())
                .toList();

        configuration.setAllowedOrigins(allowedOrigins);
        // 관리자 키워드 활성/비활성 전환 API가 PATCH를 사용하므로 CORS preflight에서 PATCH도 허용합니다.
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("*"));
        configuration.setAllowCredentials(true);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
