# Frontend React Module Guide

이 문서는 `frontend-react` 모듈의 로컬 실행과 라우트 참고용 문서입니다.

프로젝트의 단일 기준 문서는 Notion의 보고서 페이지이고, 이 문서는 React 대시보드 보조 문서로만 사용합니다.

## 목적

- 트렌드 대시보드
- 키워드 상세
- 카테고리 분석
- 기사 목록과 히스토리
- 내정보와 관리자 화면

## 자주 쓰는 명령

- `npm start`
- `npm test`
- `npm run build`

## 주요 라우트

- `/`
- `/keywords/:keyword`
- `/categories/:categorySlug`
- `/articles`
- `/history`
- `/history/:keyword`
- `/my-info`
- `/admin`

## 문서 기준

- 화면 이름과 상태 표기는 Notion 기준 문서를 따릅니다.
- 라우트나 화면 구성이 바뀌면 README와 Notion 보고서를 같이 갱신합니다.

## v2 static 모드 (서버 없이 정적 JSON으로 실행)

v2는 GitHub Pages에 화면과 정적 JSON(`contracts/site`)을 함께 배포합니다. 자세한 구조는 [`docs/v2/DESIGN.md`](../docs/v2/DESIGN.md) 6절을 봅니다.

| 빌드 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `REACT_APP_DATA_MODE` | (없음 = API 모드) | `static`이면 `src/api/staticTrendApi.js`가 정적 JSON을 읽음 |
| `REACT_APP_STATIC_DATA_BASE` | `${PUBLIC_URL}/data` | 정적 JSON 위치 |
| `PUBLIC_URL` | (없음) | Pages 하위 경로. 예: `/trend-analyzer-portfolio` |

- `npm run start:static`: `fixtures/site/data`를 `public/data`로 복사하고 static 모드 개발 서버를 띄웁니다. 다른 디렉터리는 `STATIC_FIXTURE_DIR=<dir>`로 지정합니다.
- 배포 빌드: `REACT_APP_DATA_MODE=static PUBLIC_URL=/trend-analyzer-portfolio npm run build` 후 정적 JSON을 `build/data/`에 복사합니다.
- 화면 캡처: 위 빌드 후 `node scripts/capture-static-screens.js` → `docs/v2/screens/`
- static 모드에서는 `HashRouter`를 써서 주소가 `/trend-analyzer-portfolio/#/history?...` 형태가 됩니다(Pages에 서버 rewrite가 없어 새로고침·직접 링크를 보장하기 위함).
- 숨기는 기능: 로그인 메뉴, `/my-info`, `/admin`, 챗봇. 대신 읽기 전용 `/status`(운영 현황)를 추가하고, `meta.json`의 `freshness`가 `stale`·`down`이면 모든 화면 상단에 안내를 띄웁니다.
