# v2 작업 분할

[설계 문서](DESIGN.md)의 구조를 네 개의 병렬 작업으로 나눕니다. 각 작업은 **자기 디렉터리만 수정**하고, 다른 작업과는 `contracts/`의 스키마와 아래에 적은 CLI 인터페이스로만 만납니다. 그래서 서로의 PR을 기다리지 않고 동시에 진행할 수 있습니다.

| 작업 | 브랜치 | 소유 경로 | 산출물 |
| --- | --- | --- | --- |
| A 수집기 파일 출력 | `claude/v2-a-ingest` | `crawling-python/**` | `batch_cli.py` |
| B 변환·품질·내보내기 | `claude/v2-b-analytics` | `analytics/**` | `analytics/build_site.py`, dbt 프로젝트 |
| C 화면 static 모드 | `claude/v2-c-frontend` | `frontend-react/**` | static 어댑터, 운영 현황 화면 |
| D 운영 자동화 | `claude/v2-d-ops` | `.github/workflows/**`, `scripts/ops/**`, `docs/v2/RUNBOOK.md` | ingest·publish·ci 워크플로 |

공통 규칙

- `contracts/**`, `fixtures/**`, `docs/v2/DESIGN.md`는 통합 담당이 관리합니다. 바꿔야 하면 PR 설명 맨 위에 **계약 변경**이라고 쓰고 이유를 적습니다.
- 정답은 `fixtures/reference/v1_reference.py`와 `fixtures/site/data/`입니다. v1 Java 코드와 기준 구현이 다르다고 판단되면, 기준 구현을 고치는 커밋을 따로 만들어 계약 변경으로 표시합니다.
- 클라우드 세션은 뉴스 사이트에 접속할 수 없습니다. 테스트는 고정 데이터와 stub만 씁니다.
- 커밋 전 확인: 자기 영역 테스트, `python contracts/validate.py --raw-root fixtures/raw-root --site-dir fixtures/site/data`.
- 문서·주석·커밋 메시지는 기존 저장소처럼 한국어로 씁니다.

## 고정 인터페이스

```bash
# A가 제공, D가 호출
python crawling-python/batch_cli.py \
  --output-dir <dir>                # <dir>/raw/articles/dt=*/<runId>.jsonl, <dir>/raw/runs/dt=*/<runId>.json
  [--seen-urls <file>]              # 한 줄에 URL 하나. 없으면 제외 단계 생략
  [--max-articles N]                # 기본 MAX_NEWS_PER_BATCH 또는 50
  [--trigger schedule|workflow_dispatch|backfill|local]   # 기본 local
  [--code-version SHA]              # 기본 $GITHUB_SHA 또는 local
  [--source-fixture <json>]         # 네트워크 대신 {"naver":[...],"daum":[...],"rss":[...]} 기사 사용 (CI·오프라인 e2e)
# 종료 코드: outcome == FAILURE 이면 1, 아니면 0. 마지막 줄에 run JSON 경로를 출력

# B가 제공, D가 호출
python analytics/build_site.py \
  --raw-root <dir>                  # raw/ 를 포함한 디렉터리 (data 브랜치 체크아웃)
  --out <dir>                       # contracts/site 형태의 정적 JSON
  [--as-of YYYY-MM-DDTHH:MM:SS]     # 서울 로컬, 기본 현재
  [--seeds-dir <dir>]               # 기본 analytics/seeds, 테스트는 fixtures/seeds
  [--code-version SHA]
# 종료 코드: dbt build(테스트 포함) 실패 또는 계약 위반이면 1

# C가 제공, D가 호출
cd frontend-react && REACT_APP_DATA_MODE=static PUBLIC_URL=/trend-analyzer-portfolio npm run build
# 정적 JSON은 build/data/ 에 복사해서 배포 (C는 이 경로를 기본값으로 읽음)
```

---

## A. 수집기 파일 출력 (`crawling-python/**`)

목표: v1 `main.run_job()`과 같은 수집·검증·선택·키워드 추출을 하되, 결과를 HTTP가 아니라 `contracts/raw` 형식 파일로 쓰는 1회 실행 CLI.

해야 할 것
1. `batch_cli.py`를 위 인터페이스대로 만듭니다. `run_sources`, `find_invalid_article_reason`, `select_articles_fairly`, `keyword_extractor`를 재사용합니다. `main.py`(v1 Flask 서비스)의 동작은 바꾸지 않습니다.
2. 처리 순서: 검증 → 배치 안 URL 중복 제거 → **seen URL 제외(v2 신규)** → 채널×카테고리 순환 선택 → 키워드·요약 → 파일 쓰기. 대사식은 DESIGN 4절과 `contracts/raw/run.schema.json` 그대로입니다. `select_articles_fairly`에 `seen_urls` 선택 인자를 추가하는 식으로 기존 테스트를 깨지 않게 합니다.
3. 요약 규칙(150자 + `...`)과 키워드 추출은 v1 `article_delivery.py`와 같아야 합니다. 전처리 부분을 공용 함수로 빼서 v1 HTTP 경로와 파일 경로가 함께 쓰게 하되, v1 HTTP 동작은 그대로 둡니다.
4. 파일 규칙: `dt`는 배치 시작 시각의 서울 날짜. 0건이면 JSONL을 만들지 않습니다. 임시 파일에 쓰고 rename(원자적 쓰기). 예외가 나도 가능한 범위에서 `FAILURE` run JSON을 남깁니다.
5. KoNLPy는 지연 import해서, 테스트가 Java 없이 stub 추출기로 돌 수 있게 합니다.
6. `requirements-batch.txt`: 배치에 필요한 최소 의존성만(flask·selenium·sentence-transformers·psycopg2 제외). Python 버전은 3.12 기준으로 확인하고 README에 적습니다.
7. 사용법을 `crawling-python/README.md`에 추가합니다(없으면 새로 작성).

완료 기준
- `cd crawling-python && pytest -q` 통과 (기존 47개 포함).
- 새 테스트: `--source-fixture`로 실행한 산출물이 `contracts/validate.py`를 통과, seen URL 제외 수량과 대사식, 0건 실행, 채널 실패 시 `PARTIAL_FAILURE`, 예외 시 `FAILURE` + 종료 코드 1, 같은 배치 URL 중복, 요약 150자 경계.
- `fixtures/raw-root`와 같은 모양을 만드는 `--source-fixture` 예시 파일을 `crawling-python/tests/fixtures/`에 둡니다.

하지 않을 것: 워크플로 작성(D), dbt(B), 크롤러 선택자(CSS selector) 변경.

## B. 변환·품질·내보내기 (`analytics/**`)

목표: 원천 파일에서 v1과 같은 지표를 dbt-duckdb로 계산하고, `contracts/site` 정적 JSON을 내보내는 `build_site.py`.

해야 할 것
1. dbt-duckdb 프로젝트(버전 고정). `RAW_DATA_DIR` 아래 `raw/articles/dt=*/*.jsonl`, `raw/runs/dt=*/*.json`을 읽습니다. 파일이 하나도 없는 첫 실행에서도 빈 결과로 성공해야 합니다(freshness는 `down`).
2. 모델은 DESIGN 5절 구조를 따르고, 의미는 **`fixtures/reference/v1_reference.py`와 정확히 같아야** 합니다. 특히 v1 저장 규칙(`store_keywords`: 기사 안 대소문자 병합, 차단 키워드 제외, weight=max(1,n)), alias 해석(`KeywordNormalizer`), 24시간 두 창, 카테고리 넘는 병합, 일별 가중치, 동점 규칙.
3. alias·차단 키워드는 `--seeds-dir`로 경로를 바꿀 수 있게 합니다(dbt seed 또는 `read_csv`, 방식은 자유). 운영 초기값 `analytics/seeds/keyword_aliases.csv`에는 `AI → 인공지능`, `A.I. → 인공지능`만 넣습니다.
4. `export_site.py`: marts → 정적 JSON. 정렬은 결정적으로, UTF-8, `ensure_ascii=False`, 들여쓰기 없음.
5. `build_site.py`: dbt build(테스트 포함) → export → `contracts/validate.py` 검사까지 한 번에. 실패하면 종료 코드 1.
6. 품질 게이트는 DESIGN 5.2의 표를 dbt 테스트로 구현합니다.
7. v1 동등성: `backend-spring/src/test/.../TrendAnalysticServiceTest`, `TrendServiceTest`, `TrendEvidenceServiceTest`의 케이스를 작은 고정 입력(`analytics/tests/parity/<case>/`)으로 옮기고 기대값을 Java 단언(assert)에서 가져옵니다. 같은 입력을 기준 구현에도 넣어 세 결과(Java 기대값, 기준 구현, dbt)가 일치하는지 확인합니다.
8. 가능하면: 무작위 원천 데이터 생성기로 기준 구현과 dbt 결과를 100가지 이상 비교하는 속성 테스트.

완료 기준
- `python analytics/build_site.py --raw-root fixtures/raw-root --seeds-dir fixtures/seeds --as-of 2026-10-24T12:00:00 --out /tmp/site` 결과가 `fixtures/site/data`와 JSON 값으로 같음(`generatedAt` 제외).
- `pytest analytics` 통과, 동등성 테스트 포함.
- 빈 `raw-root`에서도 성공하고 `meta.freshness == "down"`.

하지 않을 것: React 수정(C), 워크플로(D), 원천 계약 변경 없이 수집기 수정(A).

## C. 화면 static 모드 (`frontend-react/**`)

목표: 서버 없이 정적 JSON만으로 기존 대시보드를 그대로 쓰게 하는 것. 페이지 컴포넌트 수정은 최소화합니다.

해야 할 것
1. `src/api/staticTrendApi.js`: `trendApi.js`와 같은 export, 같은 반환 형태. `trendApi.js`는 `REACT_APP_DATA_MODE === 'static'`일 때만 static 구현을 씁니다(기본은 기존 API 모드 → 기존 테스트 유지).
2. 데이터 위치 `REACT_APP_STATIC_DATA_BASE` (기본 `${PUBLIC_URL}/data`). 한 번 받은 파일은 메모리에 캐시합니다.
3. 엔드포인트 대응은 DESIGN 6절 표대로입니다. 키워드 해석은 `keywords/index.json`의 `aliasToCanonical[normalize(입력)]`, 없으면 입력 그대로. `normalize`는 v1 `KeywordNormalizer`와 같아야 합니다.
4. v1 검증 규칙을 그대로 옮깁니다: `days` 2~30, `limit` 1~5, 같은 대표 키워드 비교 거부(v1 오류 문구 그대로). 오류는 axios 오류와 같은 모양(`error.response.status`, `error.response.data`)으로 던져 기존 화면의 오류 처리가 그대로 동작하게 합니다. 화면이 어떤 필드를 읽는지 먼저 확인하세요.
5. 색인에 없는 키워드: 기사 목록은 빈 배열, 추이는 0으로 채운 N일. 오늘 날짜는 `meta.json`의 `asOf`.
6. static 모드에서 숨김: 로그인 메뉴, 내 정보·구독, 관리자 경로, 챗봇. 대신 `meta.json`·`runs/recent.json`을 읽는 읽기 전용 **운영 현황** 화면을 추가하고, `freshness`가 `stale`·`down`이면 대시보드 상단에 안내를 띄웁니다.
7. GitHub Pages 하위 경로(`/trend-analyzer-portfolio/`)에서 새로고침·직접 링크가 동작해야 합니다(BrowserRouter + 404.html 우회 또는 static 모드에서 HashRouter 중 선택, 이유를 PR에 기록).
8. 개발 편의: `npm run start:static`이 `fixtures/site/data`를 `public/data`로 복사해 띄우게 합니다(`public/data`는 gitignore).

완료 기준
- `CI=true npx react-scripts test --watchAll=false` 통과 (기존 52개 + static 어댑터 테스트).
- static 어댑터 테스트가 `fixtures/site/data`로 `fixtures/README.md`의 기대값을 확인: 인공지능 1위·score 3.4, 인공지능 vs AI 비교 거부, 모르는 키워드 0 추이, 근거 기사 5건 상한.
- `REACT_APP_DATA_MODE=static PUBLIC_URL=/trend-analyzer-portfolio npm run build` 성공.
- 가능하면 Playwright(Chromium 설치돼 있음, `executablePath: '/opt/pw-browsers/chromium'`)로 static 빌드를 띄워 주요 화면 스크린샷을 `docs/v2/screens/`에 저장.

하지 않을 것: 정적 JSON 생성(B), 배포 워크플로(D).

## D. 운영 자동화 (`.github/workflows/**`, `scripts/ops/**`)

목표: 3시간마다 수집하고, 집계·배포하고, 실패를 알리는 GitHub Actions 일체.

해야 할 것
1. `scripts/ops/init_data_branch.sh`: orphan `data` 브랜치를 README와 빈 `raw/`, `state/`로 만드는 스크립트(한 번만 실행, 이미 있으면 아무것도 안 함).
2. `scripts/ops/build_seen_urls.py`: `data` 체크아웃에서 최근 7일(`dt=` 기준) 기사 URL을 모아 `state/seen_urls.txt` 생성.
3. `scripts/ops/commit_raw.sh`: 새 원천 파일 커밋·push. non-fast-forward면 rebase 후 최대 3회 재시도. 커밋 메시지 `data: <runId> <outcome> written=<n>`.
4. `scripts/ops/alert_issue.py`: 실패 시 `pipeline-failure` 라벨 Issue 생성 또는 기존 열린 Issue에 댓글, 성공 시 자동 닫기. `GITHUB_TOKEN`과 REST API 사용.
5. 워크플로 세 개(DESIGN 7절 표). 공통: `timeout-minutes`, `concurrency`, 최소 `permissions`, pip·npm 캐시, Python 3.12·Java 21(KoNLPy).
   - `ingest.yml`: cron `17 */3 * * *` + 수동(입력: `max_articles`, `trigger`=`workflow_dispatch|backfill`).
   - `publish.yml`: ingest 완료 후(`workflow_run`, 성공·실패 모두 → 실패해도 freshness 반영), 매일 cron, 수동. `build_site.py` 실패 시 배포하지 않음.
   - `ci-v2.yml`: PR과 `claude/**` push. 수집기 pytest, analytics pytest, 계약 검증, 프론트 test+static build, 오프라인 e2e(`batch_cli --source-fixture` → `build_site` → 계약 검증 → static build). 아직 병합되지 않은 작업의 job은 `hashFiles(...)` 조건으로 건너뜁니다.
6. 예약 워크플로 60일 비활성화 대비, Pages 활성화(저장소 설정 필요) 등 사람이 해야 하는 일과 장애 대응 절차를 `docs/v2/RUNBOOK.md`에 정리합니다.
7. README에 붙일 배지 마크다운(워크플로 상태, `meta.json` freshness를 읽는 shields.io dynamic 배지)을 RUNBOOK에 적어 둡니다.

완료 기준
- `scripts/ops` 단위 테스트(pytest, GitHub API는 mock) 통과.
- `actionlint`(예: `pip install actionlint-py`)로 워크플로 검사 통과.
- A·B·C가 병합되기 전에도 `ci-v2.yml`이 초록색(해당 job 건너뜀).

하지 않을 것: 수집기·dbt·React 코드 수정. 인터페이스가 부족하면 해당 작업 PR에 요청을 남깁니다.

---

## 통합 담당 (메인 세션)

- 각 PR 리뷰·CI 대응, 계약 충돌 조정.
- M1(10/28): A·B·C·D 병합 후 `data` 브랜치 생성 → backfill 수동 실행 → 첫 배포 확인.
- 이후 README v2, ADR 보강, 설계 회고, 면접 예상 질문 문서.
