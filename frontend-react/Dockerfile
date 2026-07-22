# ==================== React 멀티스테이지 빌드 ====================

# Stage 1: 빌드 단계 - React 프로덕션 빌드
# GitHub Actions에서 linux/arm64 이미지를 만들 때 QEMU 위에서 npm build가 돌면 Illegal instruction이 발생할 수 있습니다.
# 따라서 빌드 단계는 BUILDPLATFORM, 즉 GitHub Actions 러너의 네이티브 아키텍처에서 실행합니다.
FROM --platform=$BUILDPLATFORM node:22-alpine AS builder

WORKDIR /app

# package.json, package-lock.json 복사
# 캐시 효율성을 위해 먼저 복사합니다.
COPY package*.json ./

# 의존성 설치
# package-lock.json 기준으로 재현 가능한 설치를 수행합니다.
RUN npm ci

# 프로젝트 소스 코드 복사
COPY . .

ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ARG REACT_APP_PYTHON_URL
ENV REACT_APP_PYTHON_URL=$REACT_APP_PYTHON_URL

# React 프로덕션 빌드
RUN npm run build

# ==================== Stage 2: 런타임 단계 - Nginx 서빙 ====================

# 경량 Nginx 이미지
# 최종 이미지는 GitHub Actions buildx의 platforms 값에 맞춰 linux/arm64로 생성됩니다.
FROM nginx:alpine

# Stage 1에서 빌드된 React 빌드 파일 복사
COPY --from=builder /app/build /usr/share/nginx/html

# Nginx 설정 파일 복사
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 포트 노출
EXPOSE 80

# Nginx 시작
CMD ["nginx", "-g", "daemon off;"]
