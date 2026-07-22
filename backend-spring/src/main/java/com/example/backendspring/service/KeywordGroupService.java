package com.example.backendspring.service;

import com.example.backendspring.dto.KeywordAliasRequest;
import com.example.backendspring.dto.KeywordAliasResponse;
import com.example.backendspring.dto.KeywordGroupRequest;
import com.example.backendspring.dto.KeywordGroupResponse;
import com.example.backendspring.entity.KeywordAlias;
import com.example.backendspring.entity.KeywordAliasSourceType;
import com.example.backendspring.entity.KeywordGroup;
import com.example.backendspring.repository.KeywordAliasRepository;
import com.example.backendspring.repository.KeywordGroupRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 대표 키워드 그룹과 alias를 관리하는 서비스입니다.
 *
 * <p>대표 키워드 그룹은 화면에 보여줄 기준 키워드이고, alias는 같은 의미로
 * 합산할 원본 키워드입니다. alias 변경은 트렌드 화면의 조회 결과에 바로 영향을
 * 주므로 변경 직후 캐시를 재로딩합니다.</p>
 */
@Service
@RequiredArgsConstructor
public class KeywordGroupService {

    private final KeywordGroupRepository keywordGroupRepository;
    private final KeywordAliasRepository keywordAliasRepository;
    private final KeywordAliasCacheService keywordAliasCacheService;
    private final KeywordNormalizer keywordNormalizer;

    /**
     * 모든 대표 키워드 그룹을 조회합니다.
     *
     * <p>관리자 화면에서는 비활성 그룹도 확인해야 하므로 active 조건을 걸지
     * 않습니다. 각 그룹의 alias도 함께 내려 관리자 화면에서 병합 관계를 한 번에
     * 볼 수 있게 합니다.</p>
     */
    @Transactional(readOnly = true)
    public List<KeywordGroupResponse> getGroups() {
        return keywordGroupRepository.findAll(Sort.by(Sort.Direction.ASC, "canonicalKeyword"))
                .stream()
                .map(group -> {
                    List<KeywordAlias> aliases =
                            keywordAliasRepository.findByKeywordGroupIdOrderByRawKeywordAsc(group.getId());

                    return KeywordGroupResponse.from(group, aliases);
                })
                .toList();
    }

    /**
     * 단일 대표 키워드 그룹과 연결된 alias 목록을 조회합니다.
     */
    @Transactional(readOnly = true)
    public KeywordGroupResponse getGroup(Long groupId) {
        KeywordGroup group = findGroup(groupId);
        List<KeywordAlias> aliases =
                keywordAliasRepository.findByKeywordGroupIdOrderByRawKeywordAsc(groupId);

        return KeywordGroupResponse.from(group, aliases);
    }

    /**
     * 새 대표 키워드 그룹을 생성합니다.
     *
     * <p>표시 키워드는 원문으로 저장하고, 중복 판단은 정규화 값을 기준으로 합니다.
     * 이렇게 하면 띄어쓰기나 대소문자만 다른 그룹이 중복 생성되는 것을 막을 수
     * 있습니다.</p>
     */
    @Transactional
    public KeywordGroupResponse createGroup(KeywordGroupRequest request) {
        String canonicalKeyword = requireText(request.canonicalKeyword(), "대표 키워드를 입력해주세요.");
        String normalizedCanonicalKeyword = keywordNormalizer.normalize(canonicalKeyword);

        if (keywordGroupRepository.existsByNormalizedCanonicalKeyword(normalizedCanonicalKeyword)) {
            throw new IllegalArgumentException("이미 등록된 대표 키워드입니다: " + canonicalKeyword);
        }

        LocalDateTime now = LocalDateTime.now();

        KeywordGroup group = KeywordGroup.builder()
                .canonicalKeyword(canonicalKeyword)
                .normalizedCanonicalKeyword(normalizedCanonicalKeyword)
                .description(keywordNormalizer.trimToNull(request.description()))
                .active(request.active() != null ? request.active() : true)
                .createdAt(now)
                .updatedAt(now)
                .build();

        KeywordGroup savedGroup = keywordGroupRepository.save(group);

        return KeywordGroupResponse.from(savedGroup, List.of());
    }

    /**
     * 대표 키워드 그룹의 표시명, 설명, 활성 상태를 수정합니다.
     *
     * <p>대표 키워드명이 바뀌면 alias 캐시에 저장된 대표 표시명도 바뀌어야 하므로
     * 수정 후 캐시를 재로딩합니다.</p>
     */
    @Transactional
    public KeywordGroupResponse updateGroup(Long groupId, KeywordGroupRequest request) {
        KeywordGroup group = findGroup(groupId);

        String canonicalKeyword = requireText(request.canonicalKeyword(), "대표 키워드를 입력해주세요.");
        String normalizedCanonicalKeyword = keywordNormalizer.normalize(canonicalKeyword);

        if (!group.getNormalizedCanonicalKeyword().equals(normalizedCanonicalKeyword)
                && keywordGroupRepository.existsByNormalizedCanonicalKeyword(normalizedCanonicalKeyword)) {
            throw new IllegalArgumentException("이미 등록된 대표 키워드입니다: " + canonicalKeyword);
        }

        group.setCanonicalKeyword(canonicalKeyword);
        group.setNormalizedCanonicalKeyword(normalizedCanonicalKeyword);
        group.setDescription(keywordNormalizer.trimToNull(request.description()));

        if (request.active() != null) {
            group.setActive(request.active());
        }

        group.setUpdatedAt(LocalDateTime.now());

        List<KeywordAlias> aliases =
                keywordAliasRepository.findByKeywordGroupIdOrderByRawKeywordAsc(groupId);

        keywordAliasCacheService.reload();

        return KeywordGroupResponse.from(group, aliases);
    }

    /**
     * 대표 키워드 그룹을 비활성화하고 연결된 alias도 함께 비활성화합니다.
     *
     * <p>그룹만 비활성화하고 alias를 살려두면 나중에 그룹이 다시 활성화될 때
     * 원치 않는 병합 규칙까지 복구될 수 있습니다. 그래서 그룹 비활성화는 alias
     * 비활성화와 함께 처리합니다.</p>
     */
    @Transactional
    public KeywordGroupResponse deactivateGroup(Long groupId) {
        KeywordGroup group = findGroup(groupId);
        LocalDateTime now = LocalDateTime.now();

        group.setActive(false);
        group.setUpdatedAt(now);

        List<KeywordAlias> aliases =
                keywordAliasRepository.findByKeywordGroupIdOrderByRawKeywordAsc(groupId);

        aliases.forEach(alias -> {
            alias.setActive(false);
            alias.setUpdatedAt(now);
        });

        keywordAliasCacheService.reload();

        return KeywordGroupResponse.from(group, aliases);
    }

    /**
     * 대표 키워드 그룹에 관리자 수동 alias를 추가합니다.
     *
     * <p>같은 정규화 alias가 비활성 상태로 남아 있으면 기존 행을 재사용합니다.
     * 활성 alias가 이미 있다면 하나의 alias가 여러 그룹에 동시에 연결되는 것을
     * 막기 위해 예외를 던집니다.</p>
     */
    @Transactional
    public KeywordAliasResponse addAlias(Long groupId, KeywordAliasRequest request) {
        KeywordGroup group = findGroup(groupId);

        if (!Boolean.TRUE.equals(group.getActive())) {
            throw new IllegalArgumentException("비활성 대표 키워드 그룹에는 alias를 추가할 수 없습니다.");
        }

        String rawKeyword = requireText(request.rawKeyword(), "alias 키워드를 입력해주세요.");
        String normalizedKeyword = keywordNormalizer.normalize(rawKeyword);
        LocalDateTime now = LocalDateTime.now();

        KeywordAlias alias = keywordAliasRepository.findByNormalizedKeyword(normalizedKeyword)
                .map(existingAlias -> {
                    if (Boolean.TRUE.equals(existingAlias.getActive())) {
                        throw new IllegalArgumentException("이미 활성화된 alias입니다: " + existingAlias.getRawKeyword());
                    }

                    existingAlias.setKeywordGroup(group);
                    existingAlias.setRawKeyword(rawKeyword);
                    existingAlias.setSourceType(KeywordAliasSourceType.ADMIN);
                    existingAlias.setActive(true);
                    existingAlias.setUpdatedAt(now);
                    return existingAlias;
                })
                .orElseGet(() -> KeywordAlias.builder()
                        .keywordGroup(group)
                        .rawKeyword(rawKeyword)
                        .normalizedKeyword(normalizedKeyword)
                        .sourceType(KeywordAliasSourceType.ADMIN)
                        .active(true)
                        .createdAt(now)
                        .updatedAt(now)
                        .build());

        KeywordAlias savedAlias = keywordAliasRepository.save(alias);

        keywordAliasCacheService.reload();

        return KeywordAliasResponse.from(savedAlias);
    }

    /**
     * 비활성 대표 키워드 그룹을 다시 활성화합니다.
     *
     * <p>기존 alias는 자동으로 다시 켜지지 않습니다. 과거에 잘못 묶였던 alias까지
     * 함께 복구될 수 있으므로 관리자가 alias별로 재활성화하도록 둡니다.</p>
     */
    @Transactional
    public KeywordGroupResponse activateGroup(Long groupId) {
        KeywordGroup group = findGroup(groupId);

        group.setActive(true);
        group.setUpdatedAt(LocalDateTime.now());

        List<KeywordAlias> aliases =
                keywordAliasRepository.findByKeywordGroupIdOrderByRawKeywordAsc(groupId);

        keywordAliasCacheService.reload();

        return KeywordGroupResponse.from(group, aliases);
    }

    /**
     * 비활성 alias를 다시 활성화합니다.
     */
    @Transactional
    public KeywordAliasResponse activateAlias(Long aliasId) {
        KeywordAlias alias = keywordAliasRepository.findById(aliasId)
                .orElseThrow(() -> new IllegalArgumentException("alias를 찾을 수 없습니다. id=" + aliasId));

        if (!Boolean.TRUE.equals(alias.getKeywordGroup().getActive())) {
            throw new IllegalArgumentException("비활성 대표 키워드 그룹의 alias는 활성화할 수 없습니다.");
        }

        alias.setActive(true);
        alias.setUpdatedAt(LocalDateTime.now());

        keywordAliasCacheService.reload();

        return KeywordAliasResponse.from(alias);
    }

    /**
     * alias 연결을 완전히 삭제합니다.
     *
     * <p>비활성화와 달리 행 자체를 제거하므로, 같은 alias를 다른 대표 키워드 그룹에
     * 다시 붙일 수 있습니다.</p>
     */
    @Transactional
    public void detachAlias(Long aliasId) {
        KeywordAlias alias = keywordAliasRepository.findById(aliasId)
                .orElseThrow(() -> new IllegalArgumentException("alias를 찾을 수 없습니다. id=" + aliasId));

        keywordAliasRepository.delete(alias);

        keywordAliasCacheService.reload();
    }

    /**
     * alias를 비활성화합니다.
     *
     * <p>운영 이력을 보존해야 하거나 잠시 병합에서 제외하고 싶은 경우 삭제 대신
     * 이 메서드를 사용합니다.</p>
     */
    @Transactional
    public KeywordAliasResponse deactivateAlias(Long aliasId) {
        KeywordAlias alias = keywordAliasRepository.findById(aliasId)
                .orElseThrow(() -> new IllegalArgumentException("alias를 찾을 수 없습니다. id=" + aliasId));

        alias.setActive(false);
        alias.setUpdatedAt(LocalDateTime.now());

        keywordAliasCacheService.reload();

        return KeywordAliasResponse.from(alias);
    }

    private KeywordGroup findGroup(Long groupId) {
        return keywordGroupRepository.findById(groupId)
                .orElseThrow(() -> new IllegalArgumentException("대표 키워드 그룹을 찾을 수 없습니다. id=" + groupId));
    }

    private String requireText(String value, String errorMessage) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(errorMessage);
        }

        return value.trim();
    }
}
