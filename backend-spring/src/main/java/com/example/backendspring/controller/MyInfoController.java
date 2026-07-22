package com.example.backendspring.controller;

import com.example.backendspring.dto.DiscordLinkStatusResponse;
import com.example.backendspring.dto.MySubscriptionResponse;
import com.example.backendspring.dto.SubscriptionRequest;
import com.example.backendspring.service.DiscordAccountLinkService;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.util.List;

/**
 * 내정보 화면에서 사용하는 API 컨트롤러입니다.
 *
 * 제공 기능:
 * - 내가 구독한 키워드 조회
 * - Google OAuth 웹 계정과 Discord 계정 연동
 * - Discord 계정 연동 해제
 */
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/me")
public class MyInfoController {

    private final DiscordAccountLinkService discordAccountLinkService;

    @GetMapping("/subscriptions")
    public ResponseEntity<List<MySubscriptionResponse>> getMySubscriptions(Authentication authentication) {
        return ResponseEntity.ok(discordAccountLinkService.getMySubscriptions(authentication));
    }

    @PostMapping("/subscriptions")
    public ResponseEntity<MySubscriptionResponse> createMySubscription(
            Authentication authentication,
            @Valid @RequestBody SubscriptionRequest request
    ) {
        MySubscriptionResponse response = discordAccountLinkService.createMySubscription(authentication, request.keyword());
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @DeleteMapping("/subscriptions/{subscriptionId}")
    public ResponseEntity<Void> deleteMySubscription(
            Authentication authentication,
            @PathVariable Long subscriptionId
    ) {
        discordAccountLinkService.deleteMySubscription(authentication, subscriptionId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/discord/link")
    public ResponseEntity<Void> startDiscordLink(HttpSession session) {
        URI discordAuthorizationUri = discordAccountLinkService.buildDiscordAuthorizationUri(session);

        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.LOCATION, discordAuthorizationUri.toString())
                .build();
    }

    @GetMapping("/discord/callback")
    public ResponseEntity<Void> handleDiscordCallback(
            @RequestParam String code,
            @RequestParam String state,
            HttpSession session,
            Authentication authentication
    ) {
        try {
            DiscordLinkStatusResponse response = discordAccountLinkService.completeDiscordLink(code, state, session, authentication);
            URI redirectUri = discordAccountLinkService.buildFrontendRedirectUri(true, response.message());

            return ResponseEntity.status(HttpStatus.FOUND)
                    .header(HttpHeaders.LOCATION, redirectUri.toString())
                    .build();
        } catch (ResponseStatusException error) {
            URI redirectUri = discordAccountLinkService.buildFrontendRedirectUri(false, error.getReason());

            return ResponseEntity.status(HttpStatus.FOUND)
                    .header(HttpHeaders.LOCATION, redirectUri.toString())
                    .build();
        } catch (Exception error) {
            // Discord API 통신 오류 등 예상하지 못한 예외도 프론트 내정보 화면으로 돌려보냅니다.
            URI redirectUri = discordAccountLinkService.buildFrontendRedirectUri(false, "Discord 계정 연동 중 오류가 발생했습니다.");

            return ResponseEntity.status(HttpStatus.FOUND)
                    .header(HttpHeaders.LOCATION, redirectUri.toString())
                    .build();
        }
    }

    @DeleteMapping("/discord/link")
    public ResponseEntity<DiscordLinkStatusResponse> unlinkDiscord(Authentication authentication) {
        return ResponseEntity.ok(discordAccountLinkService.unlinkDiscord(authentication));
    }
}
