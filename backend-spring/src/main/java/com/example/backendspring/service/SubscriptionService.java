package com.example.backendspring.service;

import com.example.backendspring.entity.Subscription;
import com.example.backendspring.entity.User;
import com.example.backendspring.repository.SubscriptionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/**
 * Discord slash command와 웹 내정보 화면이 같은 subscriptions row를 다루도록 하는 공통 서비스입니다.
 */
@Service
@RequiredArgsConstructor
public class SubscriptionService {

    private final SubscriptionRepository subscriptionRepository;

    @Transactional
    public Subscription subscribe(User user, String rawKeyword) {
        String keyword = normalizeKeyword(rawKeyword);

        subscriptionRepository.findByUserAndKeywordIgnoreCase(user, keyword)
                .ifPresent(existing -> {
                    throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 구독 중인 키워드입니다.");
                });

        return subscriptionRepository.save(Subscription.builder()
                .user(user)
                .keyword(keyword)
                .build());
    }

    @Transactional
    public void unsubscribeById(User user, Long subscriptionId) {
        Subscription subscription = subscriptionRepository.findByIdAndUser(subscriptionId, user)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "구독 키워드를 찾을 수 없습니다."));

        subscriptionRepository.delete(subscription);
    }

    @Transactional
    public void unsubscribeByKeyword(User user, String rawKeyword) {
        String keyword = normalizeKeyword(rawKeyword);
        Subscription subscription = subscriptionRepository.findByUserAndKeywordIgnoreCase(user, keyword)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "구독 중인 키워드가 아닙니다."));

        subscriptionRepository.delete(subscription);
    }

    private String normalizeKeyword(String rawKeyword) {
        if (rawKeyword == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "구독할 키워드를 입력해 주세요.");
        }

        String keyword = rawKeyword.trim().replaceAll("\\s+", " ");
        if (keyword.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "구독할 키워드를 입력해 주세요.");
        }
        if (keyword.length() > 100) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "키워드는 100자 이하로 입력해 주세요.");
        }

        return keyword;
    }
}
