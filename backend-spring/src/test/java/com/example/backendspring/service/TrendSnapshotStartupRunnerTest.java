package com.example.backendspring.service;

import org.junit.jupiter.api.Test;
import org.springframework.boot.DefaultApplicationArguments;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class TrendSnapshotStartupRunnerTest {

    private final TrendAnalysticService trendAnalysticService = mock(TrendAnalysticService.class);
    private final TrendSnapshotStartupRunner runner = new TrendSnapshotStartupRunner(trendAnalysticService);

    @Test
    void rebuildsTrendSnapshotOnStartup() {
        runner.run(new DefaultApplicationArguments());

        verify(trendAnalysticService).analyzeAndUpdateTrends();
    }

    @Test
    void leavesApiStartupAvailableWhenInitialRefreshFails() {
        doThrow(new IllegalStateException("temporary database failure"))
                .when(trendAnalysticService)
                .analyzeAndUpdateTrends();

        assertThatCode(() -> runner.run(new DefaultApplicationArguments()))
                .doesNotThrowAnyException();
        verify(trendAnalysticService).analyzeAndUpdateTrends();
    }
}
