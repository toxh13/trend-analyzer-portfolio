package com.example.backendspring.repository;

import com.example.backendspring.entity.KeywordRecommendationRun;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface KeywordRecommendationRunRepository extends JpaRepository<KeywordRecommendationRun, Long> {

    Optional<KeywordRecommendationRun> findFirstByActiveSlotOrderByRequestedAtDesc(Integer activeSlot);

    Optional<KeywordRecommendationRun> findFirstByTargetGroupIdOrderByRequestedAtDesc(Long targetGroupId);
}
