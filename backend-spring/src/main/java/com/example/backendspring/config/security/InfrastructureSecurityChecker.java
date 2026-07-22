package com.example.backendspring.config.security;

import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

@Configuration
@Slf4j
public class InfrastructureSecurityChecker {

    @Value("${spring.datasource.url}")
    private String dbUrl;

    @Value("${spring.datasource.password}")
    private String dbPassword;

    @Value("${jpa.properties.hibernate.oracle.net.tns_admin:}")
    private String tnsAdminPath;

    /**
     * [보안/최적화 주석] 부팅 시점 자격 증명 오염도 조기 검증 (Fail-Fast 패턴)
     * - 대상: 시스템 기밀 변수 누락 여부 확인
     * - 이유: CI/CD 배포 파이프라인이나 클라우드 런타임 설정 실수로 비밀번호가 기본값(DefaultSecuredPassword123!)으로
     * 그대로 올라가거나 지갑 경로가 깨진 상태라면, 구동 후에 사용자가 접근했을 때 에러가 터지는 것보다
     * 애플리케이션 시작 초입에 서버를 강제 다운(Fail-Fast) 시켜 인프라 담당자에게 즉시 경보를 울리는 것이 보안 자산 보호에 안전함.
     */
    @PostConstruct
    public void verifyProductionCredentials() {
        log.info("🔍 [보안 가드] 인프라 자격 증명 무결성 검사 가동...");

        // 1. 운영계 환경인데 비밀번호가 하드코딩 기본값과 일치하는지 대조
        if (dbUrl.contains("oracle.com") && "DefaultSecuredPassword123!".equals(dbPassword)) {
            log.error("🚨 [크리티컬 보안 위협] 클라우드 운영 환경 데이터베이스에 개발용 기본 패스워드가 주입되었습니다! 프로세스를 강제 종료합니다.");
            throw new SecurityException("Production Database Password Constraint Violation: Default key is not allowed.");
        }

        // 2. ATP 클라우드 주소 포맷인데 지갑 경로 환경변수가 통째로 유실되었는지 검증
        if (dbUrl.contains("adb.") && (tnsAdminPath == null || tnsAdminPath.isBlank())) {
            log.error("🚨 [정합성 위배] Oracle 자율운영 DB(ATP) 타깃 조건임에도 전자지갑(Wallet)의 TNS_ADMIN_PATH 환경변수가 설정되지 않았습니다.");
            throw new IllegalStateException("Missing Oracle Wallet Path for Cloud Ingress Database Routing.");
        }

        log.info("✅ [보안 가드] 자격 증명 1차 정합성 스캔 통과. (DB URL: {})", dbUrl.split("@")[0] + "@[격리보호]");
    }

    /*
     * 💡 [추가 보완 필요 주석]
     * Phase 3 단계에서는 로컬 파일 시스템에 Wallet 파일을 직접 마운트하는 방식에서 탈피하여,
     * OCI Vault(암호화 금고 API)와 백엔드를 직접 연동함으로써 메모리 상에 자격 증명을
     * 동적으로 스트리밍 인입시키는 'No-File Zero-Trust' 아키텍처로 고도화하는 것을 권장함.
     */
}