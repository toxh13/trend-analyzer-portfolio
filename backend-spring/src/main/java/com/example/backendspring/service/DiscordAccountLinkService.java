package com.example.backendspring.service;

import com.example.backendspring.dto.DiscordLinkStatusResponse;
import com.example.backendspring.dto.MySubscriptionResponse;
import com.example.backendspring.entity.Subscription;
import com.example.backendspring.entity.User;
import com.example.backendspring.repository.SubscriptionRepository;
import com.example.backendspring.repository.UserRepository;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * 웹 Google OAuth 계정과 Discord Bot 사용 계정을 연결하는 서비스입니다.
 *
 * 핵심 목적:
 * - Google 로그인 사용자 row(users)와 Discord Bot 사용자의 discord_user_id를 하나로 연결합니다.
 * - Discord Bot에서 이미 /subscribe로 만든 구독 데이터가 있으면 웹 사용자에게 이전합니다.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class DiscordAccountLinkService {

    private static final String DISCORD_LINK_STATE = "DISCORD_LINK_STATE";

    private final UserRepository userRepository;
    private final SubscriptionRepository subscriptionRepository;
    private final SubscriptionService subscriptionService;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${app.discord.oauth.client-id:}")
    private String clientId;

    @Value("${app.discord.oauth.client-secret:}")
    private String clientSecret;

    @Value("${app.discord.oauth.redirect-uri:}")
    private String redirectUri;

    @Value("${app.discord.oauth.success-redirect-uri:http://localhost:3000/my-info}")
    private String successRedirectUri;

    @Value("${app.discord.oauth.authorization-uri:https://discord.com/oauth2/authorize}")
    private String authorizationUri;

    @Value("${app.discord.oauth.token-uri:https://discord.com/api/oauth2/token}")
    private String tokenUri;

    @Value("${app.discord.oauth.user-info-uri:https://discord.com/api/users/@me}")
    private String userInfoUri;

    /**
     * 내정보 화면에서 현재 로그인 사용자의 구독 키워드 목록을 조회합니다.
     */
    @Transactional(readOnly = true)
    public List<MySubscriptionResponse> getMySubscriptions(Authentication authentication) {
        User currentUser = resolveCurrentUser(authentication);

        return subscriptionRepository.findAllByUserOrderByCreatedAtDesc(currentUser)
                .stream()
                .map(subscription -> new MySubscriptionResponse(
                        subscription.getId(),
                        subscription.getKeyword(),
                        subscription.getCreatedAt()
                ))
                .toList();
    }

    /**
     * 연동된 Discord 계정과 동일한 사용자 row에 웹 구독을 즉시 저장합니다.
     * Discord Bot의 /list와 이후 알림은 같은 subscriptions 테이블을 읽으므로 별도 동기화 작업이 필요 없습니다.
     */
    @Transactional
    public MySubscriptionResponse createMySubscription(Authentication authentication, String keyword) {
        User currentUser = resolveDiscordLinkedCurrentUser(authentication);
        Subscription subscription = subscriptionService.subscribe(currentUser, keyword);

        return new MySubscriptionResponse(
                subscription.getId(),
                subscription.getKeyword(),
                subscription.getCreatedAt()
        );
    }

    @Transactional
    public void deleteMySubscription(Authentication authentication, Long subscriptionId) {
        User currentUser = resolveDiscordLinkedCurrentUser(authentication);
        subscriptionService.unsubscribeById(currentUser, subscriptionId);
    }

    /**
     * Discord OAuth 인증 페이지로 이동할 URL을 생성합니다.
     * state 값을 세션에 저장해 callback 요청이 사용자가 시작한 요청인지 검증합니다.
     */
    public URI buildDiscordAuthorizationUri(HttpSession session) {
        validateDiscordOAuthConfig();

        String state = UUID.randomUUID().toString();
        session.setAttribute(DISCORD_LINK_STATE, state);

        return UriComponentsBuilder.fromUriString(authorizationUri)
                .queryParam("client_id", clientId)
                .queryParam("redirect_uri", redirectUri)
                .queryParam("response_type", "code")
                .queryParam("scope", "identify")
                .queryParam("state", state)
                .build()
                .encode()
                .toUri();
    }

    /**
     * Discord OAuth callback을 처리하고 현재 로그인 사용자에 discord_user_id를 연결합니다.
     */
    @Transactional
    public DiscordLinkStatusResponse completeDiscordLink(String code, String state, HttpSession session, Authentication authentication) {
        validateState(session, state);

        User currentUser = resolveCurrentUser(authentication);
        Map<String, Object> tokenResponse = requestDiscordAccessToken(code);
        String accessToken = String.valueOf(tokenResponse.get("access_token"));

        if (accessToken == null || accessToken.isBlank() || "null".equals(accessToken)) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Discord access token을 가져오지 못했습니다.");
        }

        Map<String, Object> discordUser = requestDiscordUser(accessToken);
        String discordUserId = String.valueOf(discordUser.get("id"));
        String discordUsername = Optional.ofNullable(discordUser.get("global_name"))
                .or(() -> Optional.ofNullable(discordUser.get("username")))
                .map(String::valueOf)
                .orElse("Discord 사용자");

        if (discordUserId == null || discordUserId.isBlank() || "null".equals(discordUserId)) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Discord 사용자 ID를 가져오지 못했습니다.");
        }

        Optional<User> existingDiscordUser = userRepository.findByDiscordUserId(discordUserId);

        // 이미 같은 웹 사용자에게 연결되어 있으면 별도 병합 없이 성공 처리합니다.
        if (existingDiscordUser.isPresent() && existingDiscordUser.get().getId().equals(currentUser.getId())) {
            return new DiscordLinkStatusResponse(true, discordUserId, "이미 Discord 계정이 연동되어 있습니다.");
        }

        existingDiscordUser.ifPresent(discordOnlyUser -> mergeDiscordOnlyUserIntoCurrentUser(discordOnlyUser, currentUser));

        currentUser.setDiscordUserId(discordUserId);

        // 웹 사용자 이름이 비어 있으면 Discord 이름을 보조 표시명으로 사용합니다.
        if (currentUser.getUsername() == null || currentUser.getUsername().isBlank()) {
            currentUser.setUsername(discordUsername);
        }

        userRepository.save(currentUser);
        log.info("Discord 계정 연동 완료 - userId={}, discordUserId={}", currentUser.getId(), discordUserId);

        return new DiscordLinkStatusResponse(true, discordUserId, "Discord 계정 연동이 완료되었습니다.");
    }

    /**
     * 현재 웹 사용자와 Discord 연결을 해제합니다.
     * 구독 키워드는 사용자 데이터 보존을 위해 삭제하지 않습니다.
     */
    @Transactional
    public DiscordLinkStatusResponse unlinkDiscord(Authentication authentication) {
        User currentUser = resolveCurrentUser(authentication);
        String previousDiscordUserId = currentUser.getDiscordUserId();

        currentUser.setDiscordUserId(null);
        userRepository.save(currentUser);

        log.info("Discord 계정 연동 해제 - userId={}, previousDiscordUserId={}", currentUser.getId(), previousDiscordUserId);
        return new DiscordLinkStatusResponse(false, null, "Discord 계정 연동을 해제했습니다.");
    }

    public URI buildFrontendRedirectUri(boolean success, String message) {
        return UriComponentsBuilder.fromUriString(successRedirectUri)
                .queryParam("discordLink", success ? "success" : "failed")
                .queryParam("message", message)
                .build()
                .encode()
                .toUri();
    }

    private void validateDiscordOAuthConfig() {
        if (clientId.isBlank() || clientSecret.isBlank() || redirectUri.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Discord OAuth 환경변수(DISCORD_OAUTH_CLIENT_ID, DISCORD_OAUTH_CLIENT_SECRET, DISCORD_OAUTH_REDIRECT_URI)가 필요합니다."
            );
        }
    }

    private void validateState(HttpSession session, String state) {
        Object savedState = session.getAttribute(DISCORD_LINK_STATE);
        session.removeAttribute(DISCORD_LINK_STATE);

        if (savedState == null || state == null || !savedState.toString().equals(state)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Discord OAuth state 검증에 실패했습니다.");
        }
    }

    private Map<String, Object> requestDiscordAccessToken(String code) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("client_id", clientId);
        body.add("client_secret", clientSecret);
        body.add("grant_type", "authorization_code");
        body.add("code", code);
        body.add("redirect_uri", redirectUri);

        ResponseEntity<Map> response = restTemplate.postForEntity(
                tokenUri,
                new HttpEntity<>(body, headers),
                Map.class
        );

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Discord token API 호출에 실패했습니다.");
        }

        return response.getBody();
    }

    private Map<String, Object> requestDiscordUser(String accessToken) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(accessToken);

        ResponseEntity<Map> response = restTemplate.exchange(
                userInfoUri,
                HttpMethod.GET,
                new HttpEntity<>(headers),
                Map.class
        );

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Discord 사용자 정보 API 호출에 실패했습니다.");
        }

        return response.getBody();
    }

    private void mergeDiscordOnlyUserIntoCurrentUser(User discordOnlyUser, User currentUser) {
        // 같은 row라면 병합할 필요가 없습니다.
        if (discordOnlyUser.getId().equals(currentUser.getId())) {
            return;
        }

        List<Subscription> subscriptions = subscriptionRepository.findAllByUser(discordOnlyUser);

        for (Subscription subscription : subscriptions) {
            boolean alreadyExists = subscriptionRepository.existsByUserAndKeyword(currentUser, subscription.getKeyword());

            if (alreadyExists) {
                // 같은 키워드를 이미 구독 중이면 중복 row를 제거합니다.
                subscriptionRepository.delete(subscription);
            } else {
                // Discord Bot 전용 사용자에게 있던 구독을 현재 웹 사용자에게 이전합니다.
                subscription.setUser(currentUser);
                subscriptionRepository.save(subscription);
            }
        }

        // users.discord_user_id에는 unique 제약이 있으므로 기존 Discord 전용 row에서 먼저 값을 제거합니다.
        discordOnlyUser.setDiscordUserId(null);
        userRepository.saveAndFlush(discordOnlyUser);
    }

    private User resolveCurrentUser(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated() || !(authentication.getPrincipal() instanceof OAuth2User oauth2User)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다.");
        }

        Object internalUserId = oauth2User.getAttributes().get("internalUserId");
        if (internalUserId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "현재 로그인 사용자 정보를 확인할 수 없습니다.");
        }

        Long userId = Long.valueOf(String.valueOf(internalUserId));
        return userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "사용자 정보를 찾을 수 없습니다."));
    }

    private User resolveDiscordLinkedCurrentUser(Authentication authentication) {
        User currentUser = resolveCurrentUser(authentication);
        if (currentUser.getDiscordUserId() == null || currentUser.getDiscordUserId().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "웹에서 구독을 관리하려면 Discord 계정 연동이 필요합니다.");
        }
        return currentUser;
    }
}
