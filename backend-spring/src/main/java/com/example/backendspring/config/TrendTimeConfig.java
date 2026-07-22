package com.example.backendspring.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.ZoneId;

@Configuration
public class TrendTimeConfig {

    @Bean
    public Clock trendClock() {
        return Clock.system(ZoneId.of("Asia/Seoul"));
    }
}
