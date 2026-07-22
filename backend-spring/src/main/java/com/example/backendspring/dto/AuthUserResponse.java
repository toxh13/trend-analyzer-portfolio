package com.example.backendspring.dto;

/**
 * 현재 웹 로그인 사용자의 상태를 프론트엔드에 전달하는 DTO입니다.
 *
 * authenticated=false이면 로그인하지 않은 사용자입니다.
 * discordLinked=false이면 웹 계정과 Discord Bot 사용자가 아직 연결되지 않은 상태입니다.
 */
public record AuthUserResponse(
        boolean authenticated,
        Long id,
        String provider,
        String email,
        String username,
        String role,
        String discordUserId,
        boolean discordLinked
) {
    public static AuthUserResponse unauthenticated() {
        return new AuthUserResponse(false, null, null, null, null, null, null, false);
    }
}
