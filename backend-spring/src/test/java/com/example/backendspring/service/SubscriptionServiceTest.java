package com.example.backendspring.service;

import com.example.backendspring.entity.Subscription;
import com.example.backendspring.entity.User;
import com.example.backendspring.repository.SubscriptionRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SubscriptionServiceTest {

    @Mock
    private SubscriptionRepository subscriptionRepository;

    @InjectMocks
    private SubscriptionService subscriptionService;

    private final User user = User.builder().id(1L).discordUserId("discord-user").build();

    @Test
    @DisplayName("공백을 정리한 키워드를 구독으로 저장한다")
    void subscribeNormalizesKeyword() {
        when(subscriptionRepository.findByUserAndKeywordIgnoreCase(user, "생성형 AI"))
                .thenReturn(Optional.empty());
        when(subscriptionRepository.save(any(Subscription.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        subscriptionService.subscribe(user, "  생성형   AI  ");

        verify(subscriptionRepository).save(argThat(subscription ->
                subscription.getUser().equals(user) && subscription.getKeyword().equals("생성형 AI")
        ));
    }

    @Test
    @DisplayName("대소문자만 다른 중복 키워드는 구독할 수 없다")
    void subscribeRejectsDuplicateKeyword() {
        when(subscriptionRepository.findByUserAndKeywordIgnoreCase(user, "LLM"))
                .thenReturn(Optional.of(Subscription.builder().user(user).keyword("llm").build()));

        assertThatThrownBy(() -> subscriptionService.subscribe(user, "LLM"))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("이미 구독 중인 키워드");
    }

    @Test
    @DisplayName("소유한 구독만 ID로 취소할 수 있다")
    void unsubscribeByIdDeletesOwnedSubscription() {
        Subscription subscription = Subscription.builder().id(10L).user(user).keyword("LLM").build();
        when(subscriptionRepository.findByIdAndUser(10L, user)).thenReturn(Optional.of(subscription));

        subscriptionService.unsubscribeById(user, 10L);

        verify(subscriptionRepository).delete(subscription);
    }
}
