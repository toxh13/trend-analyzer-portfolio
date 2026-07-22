package com.example.backendspring.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * Rebuilds the persisted trend snapshot once after application startup.
 * The hourly schedule remains responsible for subsequent refreshes.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class TrendSnapshotStartupRunner implements ApplicationRunner {

    private final TrendAnalysticService trendAnalysticService;

    @Override
    public void run(ApplicationArguments args) {
        try {
            trendAnalysticService.analyzeAndUpdateTrends();
        } catch (RuntimeException error) {
            // A temporary aggregation failure must not make the API unavailable.
            // The hourly scheduler and the admin action can retry the same idempotent rebuild.
            log.error("Initial trend snapshot refresh failed; the scheduled refresh will retry", error);
        }
    }
}
