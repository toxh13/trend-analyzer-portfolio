package com.example.backendspring.controller.admin;

import com.example.backendspring.dto.KeywordAliasRequest;
import com.example.backendspring.dto.KeywordAliasResponse;
import com.example.backendspring.dto.KeywordGroupRequest;
import com.example.backendspring.dto.KeywordGroupResponse;
import com.example.backendspring.service.KeywordGroupService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

/**
 * 대표 키워드 그룹과 alias를 관리하는 관리자 API입니다.
 *
 * <p>관리자 화면은 이 API를 통해 어떤 원본 키워드들을 하나로 합산할지
 * 결정합니다. {@code /api/v1/admin} 경로 전체는 Spring Security에서
 * {@code ROLE_ADMIN}으로 보호하므로, 이 컨트롤러는 요청 위임과 HTTP 상태
 * 매핑에 집중합니다.</p>
 */
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/admin")
public class AdminKeywordGroupController {

    private final KeywordGroupService keywordGroupService;

    /**
     * 비활성 그룹까지 포함해 모든 대표 키워드 그룹을 조회합니다.
     *
     * <p>관리자는 과거 결정 이력을 확인하고 필요하면 다시 활성화할 수 있어야
     * 하므로 비활성 데이터를 숨기지 않습니다.</p>
     */
    @GetMapping("/keyword-groups")
    public ResponseEntity<List<KeywordGroupResponse>> getGroups() {
        return ResponseEntity.ok(keywordGroupService.getGroups());
    }

    /**
     * 상세/수정 화면에서 사용할 단일 그룹과 alias 목록을 조회합니다.
     */
    @GetMapping("/keyword-groups/{groupId}")
    public ResponseEntity<KeywordGroupResponse> getGroup(
            @PathVariable Long groupId
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.getGroup(groupId));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
        }
    }

    /**
     * 새 대표 키워드 그룹을 생성합니다.
     *
     * <p>중복 검사는 서비스 계층에서 표시 키워드를 정규화한 뒤 수행합니다.</p>
     */
    @PostMapping("/keyword-groups")
    public ResponseEntity<KeywordGroupResponse> createGroup(
            @RequestBody KeywordGroupRequest request
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.createGroup(request));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * 대표 키워드 표시명, 설명, 활성 상태를 수정합니다.
     */
    @PatchMapping("/keyword-groups/{groupId}")
    public ResponseEntity<KeywordGroupResponse> updateGroup(
            @PathVariable Long groupId,
            @RequestBody KeywordGroupRequest request
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.updateGroup(groupId, request));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * 그룹과 연결된 모든 alias를 비활성화합니다.
     *
     * <p>삭제하지 않고 비활성화하는 이유는 운영 이력을 보존하고, 같은 잘못된
     * 병합이 실수로 다시 살아나는 상황을 줄이기 위해서입니다.</p>
     */
    @PatchMapping("/keyword-groups/{groupId}/deactivate")
    public ResponseEntity<KeywordGroupResponse> deactivateGroup(
            @PathVariable Long groupId
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.deactivateGroup(groupId));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
        }
    }

    /**
     * 대표 키워드 그룹 자체를 다시 활성화합니다.
     *
     * <p>기존 alias는 자동으로 활성화하지 않습니다. 잘못된 병합 규칙이 함께
     * 복구되지 않도록 관리자가 alias별로 확인해서 살리게 합니다.</p>
     */
    @PatchMapping("/keyword-groups/{groupId}/activate")
    public ResponseEntity<KeywordGroupResponse> activateGroup(
            @PathVariable Long groupId
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.activateGroup(groupId));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * 대표 키워드 그룹에 관리자 수동 alias를 추가합니다.
     */
    @PostMapping("/keyword-groups/{groupId}/aliases")
    public ResponseEntity<KeywordAliasResponse> addAlias(
            @PathVariable Long groupId,
            @RequestBody KeywordAliasRequest request
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.addAlias(groupId, request));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * 비활성 alias 하나를 다시 활성화합니다.
     */
    @PatchMapping("/keyword-aliases/{aliasId}/activate")
    public ResponseEntity<KeywordAliasResponse> activateAlias(
            @PathVariable Long aliasId
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.activateAlias(aliasId));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /**
     * alias 연결을 완전히 삭제합니다.
     *
     * <p>나중에 같은 alias를 다른 대표 키워드 그룹에 연결해야 하는 경우에는
     * 비활성화가 아니라 삭제를 사용합니다.</p>
     */
    @DeleteMapping("/keyword-aliases/{aliasId}")
    public ResponseEntity<Void> detachAlias(
            @PathVariable Long aliasId
    ) {
        try {
            keywordGroupService.detachAlias(aliasId);
            return ResponseEntity.noContent().build();
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
        }
    }

    /**
     * alias를 삭제하지 않고 비활성화합니다.
     *
     * <p>운영 이력은 남기되 더 이상 트렌드 병합에는 반영하지 않습니다.</p>
     */
    @PatchMapping("/keyword-aliases/{aliasId}/deactivate")
    public ResponseEntity<KeywordAliasResponse> deactivateAlias(
            @PathVariable Long aliasId
    ) {
        try {
            return ResponseEntity.ok(keywordGroupService.deactivateAlias(aliasId));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
        }
    }
}
