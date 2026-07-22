# 문서 안내

문서의 기준일은 2026-07-22입니다. 구현 사실은 저장소 코드와 자동 테스트를 우선하며, 운영 완료 여부는 별도로 표시합니다.

## 공개 포트폴리오 문서

| 문서 | 역할 |
|---|---|
| [`../README.md`](../README.md) | 면접관이 처음 읽는 프로젝트 요약과 실행 진입점 |
| [`portfolio-report.md`](portfolio-report.md) | 데이터 파이프라인, 지표, 설계 결정과 한계의 상세 설명 |
| [`verification-report.md`](verification-report.md) | 테스트 결과와 데이터 정확성 검증 범위 |
| [`screens.md`](screens.md) | 실제 OCI 화면 스크린샷과 화면→API 흐름 |
| [`api-reference.md`](api-reference.md) | 화면·수집·인증·관리자 API 구조 |
| [`data-model.md`](data-model.md) | Oracle ERD, grain, 제약, Flyway 구조 |
| [`../LOCAL_DOCKER.md`](../LOCAL_DOCKER.md) | 로컬 재현 절차 |
| [`../env.local.example`](../env.local.example) | 실제 비밀정보가 없는 환경변수 예시 |

공개 저장소에는 위 문서와 소스 코드만 배포하는 것을 기본으로 합니다. 실제 OCI 배포 workflow, 소셜 로그인 운영 설정, 장애 원문은 공개 패키지에서 제외합니다.

## 내부 문서

| 문서 | 역할 |
|---|---|
| [`internal-project-guide.md`](internal-project-guide.md) | 개발·배포·문서 동기화 기준과 로드맵 |
| [`document-consolidation-map.md`](document-consolidation-map.md) | Notion/기존 Markdown의 통합·폐기 근거 |
| [`troubleshooting-log.md`](troubleshooting-log.md) | 날짜별 문제 해결 원문과 재발 방지 기록 |
| [`../SOCIAL_LOGIN_SETUP.md`](../SOCIAL_LOGIN_SETUP.md) | OAuth·Discord 개발 및 운영 설정 |

## 문서 상태 정의

- **구현**: 현재 코드 경로가 존재합니다.
- **자동 검증**: 테스트 또는 빌드로 재현했습니다.
- **로컬 검증**: 로컬 DB·브라우저·Docker에서 확인했습니다.
- **운영 검증**: OCI 배포 환경에서 실제 데이터로 확인했습니다.
- **예정**: 코드와 검증이 아직 없습니다.

구현됐다는 사실만으로 운영 검증까지 끝났다고 표현하지 않습니다.
