package com.example.backendspring.dto;

/**
 * Discord 계정 연동 상태를 프론트엔드에 전달하는 응답 DTO입니다.
 */
public record DiscordLinkStatusResponse(
        boolean linked,
        String discordUserId,
        String message
) {
}
