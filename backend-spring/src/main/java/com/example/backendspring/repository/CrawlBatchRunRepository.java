package com.example.backendspring.repository;

import com.example.backendspring.entity.CrawlBatchRun;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import jakarta.persistence.LockModeType;

import java.util.List;
import java.util.Optional;

public interface CrawlBatchRunRepository extends JpaRepository<CrawlBatchRun, Long> {

    @EntityGraph(attributePaths = "channels")
    Optional<CrawlBatchRun> findByRunId(String runId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select run from CrawlBatchRun run where run.runId = :runId")
    Optional<CrawlBatchRun> findByRunIdForUpdate(@Param("runId") String runId);

    List<CrawlBatchRun> findByOrderByStartedAtDesc(Pageable pageable);
}
