# 로컬 Docker 실행 가이드

이 문서는 OCI/OCIR 배포용 `docker-compose.yml`과 별도로, 로컬 PC에서 프로젝트 전체를 Docker로 빌드하고 테스트하는 방법을 정리합니다.

## 1. 파일 구분

| 파일 | 용도 |
|---|---|
| `docker-compose.yml` | OCI VM에서 OCIR 이미지를 pull해서 실행하는 배포용 compose |
| `docker-compose.local.yml` | 로컬 PC에서 Oracle DB, backend, crawler, frontend를 직접 실행하는 compose |
| `env.local.example` | 로컬 실행에 필요한 환경변수 예시 |
| `frontend-react/Dockerfile.local` | React 로컬 개발 서버 실행용 Dockerfile |
| `frontend-react/nginx.local.conf` | 로컬 Nginx 프록시 설정 파일. 현재 local compose의 frontend hot reload 모드에서는 사용하지 않음 |
| `backend-spring/src/main/resources/application-local.yaml` | 로컬 Oracle 컨테이너 접속용 Spring profile |

## 2. 로컬 구조

로컬 실행에서는 실제 OCI Oracle ATP / Wallet을 사용하지 않습니다.

```text
React Dev Server
  → http://localhost:8080 Spring Boot backend
  → Local Oracle DB container

Python Crawler
  → Spring Boot backend
  → Local Oracle DB container
```

프론트엔드는 운영처럼 Nginx 정적 서빙을 하지 않고, `npm start` 개발 서버로 실행됩니다. 그래서 `frontend-react/src` 파일을 수정하면 브라우저에 즉시 반영됩니다.

## 3. 환경변수 파일 생성

```bash
cp env.local.example env.local
```

`env.local`은 로컬에서만 사용하는 파일입니다. GitHub에 올리지 않습니다.

기본 예시:

```env
ORACLE_PASSWORD=LocalSysPassword123
DB_USERNAME=trend_app
DB_PASSWORD=TrendAppPw123
DB_URL=jdbc:oracle:thin:@oracle-db:1521/FREEPDB1
CRAWLER_API_KEY=local-dev-crawler-key-change-me
```

## 4. 로컬 Docker 실행

```bash
docker compose -f docker-compose.local.yml --env-file env.local up --build
docker compose -f docker-compose.local.yml --env-file env.local down
```

백그라운드 실행:

```bash
docker compose -f docker-compose.local.yml --env-file env.local up --build -d
```

처음 실행할 때는 Oracle DB 컨테이너 초기화 때문에 시간이 걸릴 수 있습니다.

## 5. 프론트엔드 Hot Reload 방식

로컬 compose의 `frontend` 서비스는 다음 구조로 실행됩니다.

```text
./frontend-react  →  /app
frontend-node-modules volume  →  /app/node_modules
npm start  →  localhost:3000
```

즉, 로컬에서 아래 파일들을 수정하면 Docker 컨테이너 안의 React 개발 서버가 바로 감지합니다.

```text
frontend-react/src/App.js
frontend-react/src/components/*.js
frontend-react/src/index.css
frontend-react/src/App.css
```

수정 후 브라우저에서 `http://localhost:3000`을 보고 있으면 자동으로 화면이 갱신됩니다.

### 새 npm 패키지를 추가한 경우

`package.json`이 바뀌면 node_modules 볼륨을 다시 만들거나 frontend 이미지를 다시 빌드하는 것이 안전합니다.

```bash
docker compose -f docker-compose.local.yml --env-file env.local stop frontend
docker compose -f docker-compose.local.yml --env-file env.local up --build frontend
```

의존성 문제가 계속되면 프론트 node_modules 볼륨만 삭제합니다.

```bash
docker compose -f docker-compose.local.yml --env-file env.local down
docker volume rm crawling_project_frontend-node-modules
```

볼륨 이름은 Docker Compose 프로젝트명에 따라 다를 수 있으므로 `docker volume ls`로 확인할 수 있습니다.

## 6. 접속 주소

| 서비스 | 주소 |
|---|---|
| React Frontend Dev Server | http://localhost:3000 |
| Spring Boot Backend | http://localhost:8080 |
| Python Crawler | http://localhost:5000 |
| Local Oracle DB | localhost:1521/FREEPDB1 |

프론트엔드 개발 서버에서는 `REACT_APP_API_URL=http://localhost:8080`을 사용합니다. 그래서 브라우저가 백엔드 API를 직접 호출합니다.

## 7. 로그 확인

```bash
docker compose -f docker-compose.local.yml --env-file env.local logs -f oracle-db
```

```bash
docker compose -f docker-compose.local.yml --env-file env.local logs -f backend
```

```bash
docker compose -f docker-compose.local.yml --env-file env.local logs -f crawler
```

```bash
docker compose -f docker-compose.local.yml --env-file env.local logs -f frontend
```

## 8. 종료

```bash
docker compose -f docker-compose.local.yml --env-file env.local down
```

DB 데이터까지 완전히 초기화하고 싶다면 볼륨까지 삭제합니다.

```bash
docker compose -f docker-compose.local.yml --env-file env.local down -v
```

주의: `down -v`는 `oracle-local-data`와 `frontend-node-modules` 볼륨을 모두 삭제합니다.

## 9. 기존 방식과 달라진 점

### 이전

```text
운영용 docker-compose.yml 하나만 존재
→ OCI VM에서 OCIR 이미지 pull 기준
→ 로컬 PC에서는 실제 Oracle ATP Wallet을 붙여야 테스트 가능
→ 프론트는 빌드 후 Nginx 서빙이라 수정 즉시 반영 불가
```

### 이후

```text
운영용 docker-compose.yml 유지
+ 로컬용 docker-compose.local.yml 추가
+ 로컬 Oracle DB 컨테이너 추가
+ application-local.yaml 추가
+ React 개발 서버 기반 frontend hot reload 적용
+ frontend-react/Dockerfile.local 추가
+ env.local.example 추가
```

## 10. 중요한 운영/로컬 차이

운영 환경은 기존 `application.yaml`을 사용합니다.

```text
운영: Oracle ATP + Wallet + Flyway + ddl-auto validate
```

로컬 환경은 `application-local.yaml`을 사용합니다.

```text
로컬: Oracle DB container + JPA ddl-auto update + Flyway disabled
```

현재 `V1__.sql`과 `V2__init.sql`이 모두 주요 테이블과 시퀀스를 생성하는 구조라, 새 로컬 DB에서 Flyway를 그대로 켜면 중복 DDL 충돌 가능성이 있습니다. 그래서 로컬 프로필에서는 우선 Flyway를 끄고 JPA가 스키마를 생성하도록 했습니다.

## 11. 주의 사항

- `env.local`은 GitHub에 올리지 않습니다.
- 로컬 DB 데이터는 `oracle-local-data` Docker volume에 저장됩니다.
- 프론트엔드 의존성은 `frontend-node-modules` Docker volume에 저장됩니다.
- 운영 배포는 기존 `docker-compose.yml`을 계속 사용합니다.
- 로컬 테스트 후 DB 데이터 초기화가 필요하면 `down -v`를 사용합니다.
