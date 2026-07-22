package com.example.backendspring.config;

import com.example.backendspring.discord.DiscordCommandListener;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import net.dv8tion.jda.api.JDA;
import net.dv8tion.jda.api.JDABuilder;
import net.dv8tion.jda.api.interactions.commands.OptionType;
import net.dv8tion.jda.api.interactions.commands.build.Commands;
import net.dv8tion.jda.api.requests.GatewayIntent;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class DiscordBotConfig {

    // application.yml에 세팅한 봇 토큰 값을 가져옵니다.
    @Value("${discord.bot.token}")
    private String botToken;

    // 명령어 이벤트를 처리할 리스너 (Step 4에서 생성할 클래스입니다)
    private final DiscordCommandListener discordCommandListener;

    /**
     * JDA 객체를 Spring Bean으로 등록하여 애플리케이션 생명주기와 동기화 (최적화)
     */
    @Bean
    public JDA jda() {
        try {
            JDA jda = JDABuilder.createDefault(botToken)
                    // 챗봇 명령어와 메시지 읽기 권한 부여
                    .enableIntents(GatewayIntent.MESSAGE_CONTENT, GatewayIntent.GUILD_MESSAGES)
                    // 우리가 만든 이벤트 리스너 등록
                    .addEventListeners(discordCommandListener)
                    .build();

            // 디스코드 서버가 켜질 때까지 대기 (Blocking)
            jda.awaitReady();

            // 🌟 챗봇 슬래시 명령어(/) 등록
            // 디스코드 서버에 우리가 사용할 명령어를 미리 알려주는 작업입니다.
            jda.updateCommands().addCommands(
                    Commands.slash("subscribe", "관심 있는 IT 트렌드 키워드를 구독합니다.")
                            .addOption(OptionType.STRING, "keyword", "구독할 키워드 (예: LLM, 클라우드)", true),
                    Commands.slash("unsubscribe", "구독 중인 IT 트렌드 키워드를 취소합니다.")
                            .addOption(OptionType.STRING, "keyword", "구독 취소할 키워드", true),
                    Commands.slash("list", "현재 구독 중인 트렌드 키워드 목록을 확인합니다."),
                    Commands.slash("today", "오늘 수집된 실시간 핫 트렌드 뉴스를 확인합니다.")
            ).queue();

            log.info("🤖 디스코드 봇(JDA)이 성공적으로 구동되었습니다!");
            return jda;

        } catch (Exception e) {
            log.error("🚨 디스코드 봇 구동 중 오류 발생: {}", e.getMessage());
            throw new RuntimeException("디스코드 봇 구동 실패", e);
        }
    }
}
