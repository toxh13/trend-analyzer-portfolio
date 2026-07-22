package com.example.backendspring.discord;

import com.example.backendspring.dto.TrendingResponseDto;
import com.example.backendspring.entity.Subscription;
import com.example.backendspring.entity.User;
import com.example.backendspring.repository.SubscriptionRepository;
import com.example.backendspring.repository.UserRepository;
import com.example.backendspring.service.SubscriptionService;
import com.example.backendspring.service.TrendService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;
import net.dv8tion.jda.api.interactions.commands.OptionMapping;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Component
@RequiredArgsConstructor
@Slf4j
public class DiscordCommandListener extends ListenerAdapter {
    private final UserRepository userRepository;
    private final SubscriptionRepository subscriptionRepository;
    private final SubscriptionService subscriptionService;
    private final TrendService trendService;

    @Override
    @Transactional
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {

        // 1. 어떤 명령어가 들어왔는지 확인
        String commandName = event.getName();

        // 2. 명령어를 입력한 유저의 디스코드 고유 ID 추출 (매우 중요: DB 식별자)
        String discordUserId = event.getUser().getId();
        String username = event.getUser().getName();

        log.info("💬 디스코드 명령어 수신 - 명령어: [{}], 사용자: {} ({})", commandName, username, discordUserId);


        // 3. 명령어 분기 처리
        switch (commandName) {
            case "subscribe":
                // 사용자가 입력한 키워드 추출
                String keyword = getKeywordOption(event);
                if (keyword == null || keyword.isBlank()) {
                    event.reply("⚠️ 구독할 키워드를 입력해 주세요.").setEphemeral(true).queue();
                    break;
                }

                User user = userRepository.findByDiscordUserId(discordUserId)
                        .orElseGet(() -> userRepository.save(
                                // DB에 없는 신규 사용자라면 User 엔티티를 생성하고 저장
                                User.builder()
                                        .discordUserId(discordUserId)
                                        .username(username)
                                        .provider("DISCORD")
                                        .role("ROLE_USER")
                                        .build()
                        ));
                try {
                    Subscription subscription = subscriptionService.subscribe(user, keyword);
                    event.reply("✅ `" + subscription.getKeyword() + "` 키워드 구독이 완료되었습니다!\n" +
                            "해당 키워드의 핫한 뉴스가 수집되면 알려드릴게요.").queue();
                } catch (org.springframework.web.server.ResponseStatusException error) {
                    event.reply("⚠️ " + error.getReason()).setEphemeral(true).queue();
                }
                break;

            case "unsubscribe":
                String unsubscribeKeyword = getKeywordOption(event);
                if (unsubscribeKeyword == null || unsubscribeKeyword.isBlank()) {
                    event.reply("⚠️ 구독 취소할 키워드를 입력해 주세요.").setEphemeral(true).queue();
                    break;
                }
                userRepository.findByDiscordUserId(discordUserId).ifPresentOrElse(
                        existingUser -> {
                            try {
                                subscriptionService.unsubscribeByKeyword(existingUser, unsubscribeKeyword);
                                event.reply("✅ `" + unsubscribeKeyword.trim() + "` 키워드 구독을 취소했습니다.").queue();
                            } catch (org.springframework.web.server.ResponseStatusException error) {
                                event.reply("⚠️ " + error.getReason()).setEphemeral(true).queue();
                            }
                        },
                        () -> event.reply("⚠️ 구독 중인 키워드가 없습니다.").setEphemeral(true).queue()
                );
                break;

            case "list":
                userRepository.findByDiscordUserId(discordUserId).ifPresentOrElse(
                        user1 -> {
                            List<Subscription> subscriptions = subscriptionRepository.findAllByUser(user1);
                            if (subscriptions.isEmpty()) {
                                event.reply("📋 현재 구독 중인 키워드가 없습니다.").queue();
                            } else {
                                // 4. [최적화] Stream API를 활용해 반복문 오버헤드 없이 문자열 조합 (예: "`LLM`, `클라우드`")
                                String keywordList = subscriptions.stream()
                                        .map(sub -> "`" + sub.getKeyword() + "`")
                                        .collect(Collectors.joining(", "));
                                event.reply("📋 현재 구독 중인 키워드 목록:\n" + keywordList).queue();
                            }
                        },
                        () ->       { event.reply("⚠️ 아직 시스템에 등록되지 않으셨습니다.\n먼저 `/subscribe [키워드]` 명령어를 통해 구독을 시작해 주세요!")
                                .setEphemeral(true).queue();}
                );
                break;

            case "today":
                // 1. 기존에 만들어둔 TrendService를 재사용하여 전체 트렌드 상위 20개 조회
                List<TrendingResponseDto> Top20News = trendService.getTop20Trend();

                // 2. [예외 처리] 크롤러가 아직 돌지 않아 데이터가 없는 경우의 방어 로직
                if(Top20News==null || Top20News.isEmpty()) {
                    event.reply("⚠️ 오늘의 핫 트렌드 뉴스가 아직 수집되지 않았습니다. 잠시 후 다시 시도해 주세요.").queue();
                    return;
                }
                // 3. [최적화 & UX] 디스코드 채팅창 도배를 막기 위해 상위 5개만 끊어서(limit) 출력

                String todayTrendMessage = Top20News.stream()
                                .limit(5)
                                .map(dto -> String.format(" '%d위' **%s** (%.2f점 | %d회 언급)",
                                                dto.getRank(),dto.getKeyword(), dto.getScore(), dto.getMention_count()))
                        .collect(Collectors.joining("\n"));

                event.reply("📰 **오늘의 IT/테크 핫 트렌드 TOP 5** 📰\n\n"
                        + todayTrendMessage
                        + "\n\n💡 `/subscribe [키워드]`로 구독하고, `/unsubscribe [키워드]`로 취소할 수 있어요.").queue();
                break;

            default:
                event.reply("❌ 알 수 없는 명령어입니다.").setEphemeral(true).queue();
        }
    }

    private String getKeywordOption(SlashCommandInteractionEvent event) {
        OptionMapping keywordOption = event.getOption("keyword");
        return keywordOption == null ? null : keywordOption.getAsString();
    }
}
