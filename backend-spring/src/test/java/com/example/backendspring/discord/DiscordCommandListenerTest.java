package com.example.backendspring.discord;

import com.example.backendspring.repository.SubscriptionRepository;
import com.example.backendspring.repository.UserRepository;
import com.example.backendspring.service.SubscriptionService;
import com.example.backendspring.service.TrendService;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.mockito.Mockito.RETURNS_DEEP_STUBS;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DiscordCommandListenerTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private SubscriptionRepository subscriptionRepository;

    @Mock
    private SubscriptionService subscriptionService;

    @Mock
    private TrendService trendService;

    @InjectMocks
    private DiscordCommandListener listener;

    @Test
    @DisplayName("subscribe 키워드 옵션이 없으면 안내하고 DB를 조회하지 않는다")
    void subscribeWithoutKeywordIsRejectedBeforeDatabaseAccess() {
        SlashCommandInteractionEvent event = commandEvent("subscribe");

        listener.onSlashCommandInteraction(event);

        verify(event).reply("⚠️ 구독할 키워드를 입력해 주세요.");
        verifyNoInteractions(userRepository, subscriptionRepository, subscriptionService, trendService);
    }

    @Test
    @DisplayName("unsubscribe 키워드 옵션이 없으면 안내하고 DB를 조회하지 않는다")
    void unsubscribeWithoutKeywordIsRejectedBeforeDatabaseAccess() {
        SlashCommandInteractionEvent event = commandEvent("unsubscribe");

        listener.onSlashCommandInteraction(event);

        verify(event).reply("⚠️ 구독 취소할 키워드를 입력해 주세요.");
        verifyNoInteractions(userRepository, subscriptionRepository, subscriptionService, trendService);
    }

    private SlashCommandInteractionEvent commandEvent(String commandName) {
        SlashCommandInteractionEvent event = mock(SlashCommandInteractionEvent.class, RETURNS_DEEP_STUBS);
        when(event.getName()).thenReturn(commandName);
        when(event.getUser().getId()).thenReturn("discord-user-1");
        when(event.getUser().getName()).thenReturn("tester");
        return event;
    }
}
