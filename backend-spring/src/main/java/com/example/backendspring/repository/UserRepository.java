package com.example.backendspring.repository;

import com.example.backendspring.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    Optional<User> findByDiscordUserId(String discordUserId);

    // 소셜 로그인 사용자를 provider + providerId 조합으로 찾습니다.
    // 예: provider=GOOGLE, providerId=Google sub 값
    Optional<User> findByProviderAndProviderId(String provider, String providerId);

    // 이메일이 같은 기존 웹 계정이 있을 때 소셜 계정과 연결할 수 있도록 첫 번째 항목만 조회합니다.
    Optional<User> findFirstByEmail(String email);
}
