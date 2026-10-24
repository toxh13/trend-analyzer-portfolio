# v2 공용 고정 데이터

모든 작업(A·B·C·D)이 같은 입력과 같은 정답을 보고 개발·테스트하기 위한 데이터입니다. 기준 시각은 **`as_of = 2026-10-24T12:00:00` (Asia/Seoul)** 입니다.

| 경로 | 내용 | 만든 방법 |
| --- | --- | --- |
| `raw-root/raw/` | 원천 파일 (실행 4회, 기사 18줄) | `python fixtures/build_raw_fixtures.py` |
| `seeds/` | 고정 데이터 전용 alias·차단 키워드 | 직접 작성 |
| `reference/v1_reference.py` | v1 Spring 집계 로직의 Python 직역 (정답 계산기) | 직접 작성 |
| `site/data/` | 위 입력으로 계산한 정답 정적 JSON | 아래 명령 |

```bash
python fixtures/reference/v1_reference.py \
  --raw-root fixtures/raw-root --seeds fixtures/seeds \
  --as-of 2026-10-24T12:00:00 --generated-at 2026-10-24T03:00:00Z \
  --code-version fixture --out fixtures/site/data
python contracts/validate.py --raw-root fixtures/raw-root --site-dir fixtures/site/data
```

> dbt 테스트는 `analytics/seeds/`(운영용)가 아니라 **`fixtures/seeds/`** 를 써야 합니다. 운영 alias가 늘어도 고정 데이터 테스트가 깨지지 않게 하기 위함입니다.

## 집계 창

- current: `[2026-10-23 12:00, 2026-10-24 12:00)`
- previous: `[2026-10-22 12:00, 2026-10-23 12:00)`
- 30일 추이: `2026-09-25` ~ `2026-10-24`(오늘, 12:00까지라 partial)

## 시나리오별 기대값

| 시나리오 | 데이터 | 기대 결과 |
| --- | --- | --- |
| alias 병합 | 시드 `AI → 인공지능`. 기사 6(AI), 11·12·13(인공지능), 14(경제, AI) | 인공지능: mention 4 (IT 3 + 경제 1), velocity +3, score 3.4, 목록 1위, category `IT/과학` |
| 한 기사에 alias 여러 개 | 기사 12에 `인공지능`, `AI` 둘 다 | 기사 1건으로만 센다 |
| 카테고리 넘는 합산 | 반도체 IT(cur 3, prev 2) + 경제(cur 1) | mention 4, velocity +2, score 2.8 = 1.8 + 1.0 |
| 감소 키워드 | 환율 prev 3 (7·8·9), cur 1 (15) | velocity −2, score −0.8, `fallingKeyword` |
| 변화 없음 | 증시 prev 1 (7), cur 1 (14) | `changeType: same`, score 0.4 |
| current 0건 | 보안 prev 1 (5) | 스냅샷에는 있지만 목록에서 제외(mention 0). 상세 파일 없음(30일 1건, 목록에 없음) |
| 차단 키워드 | 기사 3의 `속보` | 저장 단계에서 제외. 어떤 집계에도 없음 |
| 기사 안 대소문자 중복 | 기사 2의 `AI`(2), `ai`(1) | `AI` weight 3 하나로 저장 (v1 `CrawlingService` 규칙) |
| 다른 실행의 같은 URL | R2·R3 모두 기사 10 | 먼저 수집된 R2 행만 남음 (R3 제목 "다시 수집된…"은 어디에도 없어야 함) |
| as_of 이후 발행 | 기사 17 (`2026-10-24T13:00`) | 모든 집계·목록·상세에서 제외 |
| 48시간 밖·30일 안 | 기사 1~3 (10/22 오전), 16 (10/17) | 스냅샷 제외, 일별 추이·상세 기사에는 포함 |
| 0건 실행 | R4 `EMPTY` | run JSON만 있고 JSONL 파일 없음. `runs/recent.json`에 포함 |
| 부분 실패 실행 | R2 `PARTIAL_FAILURE` (daum 채널 FAILURE) | 신선도 계산에서 성공으로 인정 |

대시보드 통계(전체): `analyzedArticles 6`, `trackedKeywords 6`, rising `인공지능(+3)`, falling `환율(−2)`. 신선도: 마지막 성공 R3 완료 `2026-10-24T00:20:30Z` → as_of까지 2.66시간 → `ok`.

## v1과 일부러 다르게 한 점

`reference/v1_reference.py` 맨 위 docstring과 [설계 문서 5.1절](../docs/v2/DESIGN.md)에 정리했습니다. 요약하면 동점·카테고리 선택을 결정적으로 만들고, as_of 이후 데이터를 빼고, float 오차를 반올림했습니다.
