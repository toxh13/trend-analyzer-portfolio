package com.example.backendspring.repository;

import com.example.backendspring.entity.Subscription;
import com.example.backendspring.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SubscriptionRepository extends JpaRepository<Subscription, Long> {
    boolean existsByUserAndKeyword(User user, String keyword);

    Optional<Subscription> findByUserAndKeywordIgnoreCase(User user, String keyword);

    Optional<Subscription> findByIdAndUser(Long id, User user);

    List<Subscription> findAllByUser(User user);

    // 내정보 화면에서는 최신 구독 키워드가 먼저 보이도록 정렬합니다.
    List<Subscription> findAllByUserOrderByCreatedAtDesc(User user);
}
