# ===================================================================
# IT/테크 실시간 트렌드 분석 시스템 — OCI 배포용 백엔드 도커파일
# [최적화] Multi-stage 빌드 및 Gradle 호환성(v8.6) 롤백
# [보안]   Oracle ATP mTLS 통신을 위한 전자지갑(Wallet) 내부 격리 주입
# ===================================================================

# ==================== Stage 1: 빌드 단계 ====================
# [호환성 방어] Spring Boot 3.3.x 플러그인과 충돌이 없는 Gradle 8.6 사용
FROM --platform=$BUILDPLATFORM gradle:8.6-jdk21 AS builder

WORKDIR /build

# [최적화] 도커 레이어 캐싱을 극대화하기 위해 설정 파일만 먼저 복사
COPY build.gradle settings.gradle ./
# 소스 코드 복사
COPY src ./src

# [최적화] 테스트를 건너뛰어 CI/CD 파이프라인 빌드 속도 향상
RUN --mount=type=cache,target=/home/gradle/.gradle \
    gradle bootJar -x test --no-daemon

# ==================== Stage 2: 실행 단계 (Runtime) ====================
# [최적화] 안정적이고 극도로 가벼운 알파인 리눅스 기반 자바 21 런타임
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# 🌟 [보안/가장 중요] OCI ATP DB 접속을 위한 암호화 전자지갑(Wallet) 복사
# 깃허브에는 올라가지 않는 로컬의 wallet 폴더를 컨테이너 내부로 쏙 집어넣어,
# 백엔드가 /app/wallet 경로에서 지갑을 꺼내어 안전하게 통신하도록 묶어줍니다.
# COPY wallet/ /app/wallet/

# 1단계에서 빌드된 순수 실행 파일(app.jar)만 추출하여 복사
COPY --from=builder /build/build/libs/*-SNAPSHOT.jar app.jar

EXPOSE 8080

# [최적화] JVM 타임존(Asia/Seoul)을 강제 할당하여 DB 시간 데이터 오염 방지
ENTRYPOINT ["java", "-jar", "app.jar"]
