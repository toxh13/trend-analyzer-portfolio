package com.example.backendspring.controller;

import com.example.backendspring.dto.AuthUserResponse;
import com.example.backendspring.entity.User;
import com.example.backendspring.repository.UserRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.Optional;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/auth")
@Slf4j
public class AuthController {

    private final UserRepository userRepository;

    @GetMapping("/me")
    public ResponseEntity<AuthUserResponse> getCurrentUser(
            Authentication authentication,
            HttpServletRequest request
    ) {
        // [보완] MVC argument resolver가 Authentication을 넘기지 못하는 상황까지 방어하기 위해
        // SecurityContextHolder에서 한 번 더 현재 인증 정보를 조회합니다.
        Authentication currentAuthentication = authentication != null
                ? authentication
                : SecurityContextHolder.getContext().getAuthentication();

        if (currentAuthentication == null
                || !currentAuthentication.isAuthenticated()
                || !(currentAuthentication.getPrincipal() instanceof OAuth2User oauth2User)) {
            logAuthState("현재 요청은 OAuth2 로그인 사용자로 인식되지 않습니다.", request, currentAuthentication);
            return ResponseEntity.ok(AuthUserResponse.unauthenticated());
        }

        Object internalUserId = oauth2User.getAttributes().get("internalUserId");
        if (internalUserId == null) {
            logAuthState("OAuth2 principal은 존재하지만 internalUserId가 없습니다.", request, currentAuthentication);
            return ResponseEntity.ok(AuthUserResponse.unauthenticated());
        }

        Long userId = Long.valueOf(String.valueOf(internalUserId));
        Optional<User> user = userRepository.findById(userId);

        if (user.isEmpty()) {
            log.warn("OAuth2 principal의 internalUserId={}에 해당하는 users row를 찾지 못했습니다.", userId);
        }

        return ResponseEntity.ok(user
                .map(this::toResponse)
                .orElseGet(AuthUserResponse::unauthenticated));
    }

    @GetMapping("/providers")
    public ResponseEntity<Map<String, String>> getLoginProviders(HttpServletRequest request) {
        String baseUrl = request.getScheme() + "://" + request.getServerName()
                + (request.getServerPort() == 80 || request.getServerPort() == 443 ? "" : ":" + request.getServerPort());

        return ResponseEntity.ok(Map.of(
                "google", baseUrl + "/oauth2/authorization/google"
        ));
    }

    @GetMapping("/csrf")
    public ResponseEntity<Map<String, String>> getCsrfToken(CsrfToken csrfToken) {
        return ResponseEntity.ok(Map.of(
                "token", csrfToken.getToken(),
                "headerName", csrfToken.getHeaderName()
        ));
    }

    @PostMapping("/logout")
    public ResponseEntity<AuthUserResponse> logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }

        SecurityContextHolder.clearContext();
        return ResponseEntity.ok(AuthUserResponse.unauthenticated());
    }

    private void logAuthState(String message, HttpServletRequest request, Authentication authentication) {
        HttpSession session = request.getSession(false);
        Object securityContext = session != null ? session.getAttribute("SPRING_SECURITY_CONTEXT") : null;
        Object principal = authentication != null ? authentication.getPrincipal() : null;

        log.warn(
                "{} sessionExists={}, authenticationClass={}, principalClass={}, authenticated={}, securityContextExists={}",
                message,
                session != null,
                authentication != null ? authentication.getClass().getName() : null,
                principal != null ? principal.getClass().getName() : null,
                authentication != null && authentication.isAuthenticated(),
                securityContext != null
        );
    }

    private AuthUserResponse toResponse(User user) {
        boolean discordLinked = user.getDiscordUserId() != null && !user.getDiscordUserId().isBlank();

        return new AuthUserResponse(
                true,
                user.getId(),
                user.getProvider(),
                user.getEmail(),
                user.getUsername(),
                user.getRole(),
                user.getDiscordUserId(),
                discordLinked
        );
    }
}
