# 검증 보고서

## 1. 검증 기준

검증 결과를 다음 세 단계로 구분합니다.

| 단계 | 의미 |
|---|---|
| 자동 검증 | 단위·통합 테스트와 빌드가 통과함 |
| 로컬 통합 검증 | Docker·Oracle Free·브라우저에서 흐름을 확인함 |
| 운영 검증 | OCI와 실제 뉴스 데이터에서 결과를 확인함 |

자동 테스트 통과만으로 데이터 의미나 외부 수집 성공까지 보장한다고 표현하지 않습니다.

## 2. 2026-07-22 자동 검증

| 모듈 | 명령 | 결과 |
|---|---|---|
| Spring Boot | `gradlew test` | 70 tests, 실패 0 |
| React | `npm test -- --watchAll=false --runInBand` | 13 suites, 51 tests 통과 |
| React build | `npm run build` | production build 성공 |
| Python | `python -m unittest discover -s tests` | 47 tests 통과 |
| Python 문법 | `python -m compileall -q .` | 성공 |

React 테스트에는 Router v7 전환 예정 경고가 있지만 현재 React Router 6 동작과 테스트 결과에는 영향을 주지 않습니다.

## 3. 데이터 정확성 계약

### 수집 단계

- 한 채널 실패가 다른 채널을 중단하지 않는지 확인
- timeout·429·5xx만 제한 재시도하고 영구적 4xx는 반복하지 않는지 확인
- 본문·발행 시각 누락 기사를 제외하는지 확인
- URL 중복 제거 후 선택 수량이 대사식과 일치하는지 확인
- 시작·완료 보고가 동일 payload 재전송에 멱등인지 확인

### 저장 단계

- `source_url` 중복 저장 방지
- 기사와 키워드의 부모·자식 저장 일관성
- `run_id`, 상태, 시간, 음수 수량, 수량 대사 DB 제약
- `trend_metrics`의 `(keyword, category)` 유일성

### 집계 단계

- 고정 `Clock`으로 현재·직전 24시간 경계 검증
- `[start, end)` 반개구간으로 경계 중복 방지
- 같은 기사 내 alias와 반복 키워드를 한 번만 집계
- 이전 구간에만 있는 키워드를 음수 변화량으로 보존
- 두 구간 모두에서 사라진 과거 스냅샷 제거
- 일별 집계의 `Asia/Seoul`, 2/7/30일, 오늘 부분 집계 검증

### 조회 단계

- 동일 대표 키워드의 두 alias 비교 요청을 400으로 거부
- 기사 근거가 날짜 반개구간과 alias 규칙을 공유
- 한 기사에 여러 alias가 있어도 `EXISTS`로 한 번만 반환
- 키워드별 최신 발행 시각과 id 순으로 최대 5건 반환

## 4. 재현 절차

```bash
# backend
cd backend-spring
./gradlew test

# frontend
cd frontend-react
npm test -- --watchAll=false --runInBand
npm run build

# crawler
cd crawling-python
python -m unittest discover -s tests
python -m compileall -q .
```

전체 로컬 환경은 다음 명령으로 실행합니다.

```bash
cp env.local.example env.local
docker compose -f docker-compose.local.yml --env-file env.local up --build
```

## 5. 운영 확인 체크리스트

- 최근 수집 실행이 `RUNNING`에서 완료 상태로 전환되는가
- 세 채널 수와 배치 합계가 DB 제약 및 화면 대사와 일치하는가
- 실패 채널이 있어도 성공 채널 기사와 키워드가 저장되는가
- 트렌드 스냅샷의 생성 시각과 기사 표본이 24시간 계약에 맞는가
- 비교 화면의 선택 날짜 수치가 근거 기사와 일치하는가
- 배포 healthcheck 성공 뒤 실제 API와 화면이 응답하는가

## 6. 검증 한계

- 외부 뉴스 전체 모집단 대비 수집률은 측정하지 않습니다.
- `backendAcknowledgedCount`와 신규 저장 건수는 같은 지표가 아닙니다.
- 자동 테스트는 실제 OAuth provider, Discord, OCIR, OCI 네트워크 장애를 재현하지 않습니다.
- 운영 검증 결과는 확인 날짜와 데이터 표본을 함께 기록해야 합니다.
