package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@Table(
        name = "users",
        indexes = {
                // provider + provider_id 조합은 소셜 로그인 사용자를 식별하는 핵심 키입니다.
                @Index(name = "idx_users_provider_provider_id", columnList = "provider, provider_id"),
                @Index(name = "idx_users_email", columnList = "email")
        }
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "user_seq")
    @SequenceGenerator(name = "user_seq", sequenceName = "USER_SEQ", allocationSize = 1)
    private Long id;

    // 웹 소셜 로그인 제공자입니다. 예: GOOGLE, KAKAO, NAVER
    @Column(name = "provider")
    private String provider;

    // 제공자가 내려주는 고유 사용자 ID입니다. Google은 sub 값을 사용합니다.
    @Column(name = "provider_id")
    private String providerId;

    @Column(name = "email")
    private String email;

    @Column(name = "role")
    private String role; // 예: "ROLE_USER"

    // Discord Bot만 사용하는 사용자는 이 값만 있어도 됩니다.
    // 웹 계정과 Discord Bot 사용 내역을 연결하려는 경우에만 웹 계정과 같은 row에 연결합니다.
    @Column(name = "discord_user_id", unique = true)
    private String discordUserId;

    @Column(name = "username")
    private String username; // 사용자 닉네임

    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;
}
