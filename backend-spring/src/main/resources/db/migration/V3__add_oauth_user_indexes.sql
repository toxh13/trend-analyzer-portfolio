-- ===================================================================
-- OAuth2 소셜 로그인 사용자 조회 최적화
-- -------------------------------------------------------------------
-- provider + provider_id 조합은 Google/Kakao/Naver 같은 소셜 로그인 사용자를
-- 식별하는 핵심 키입니다.
-- ===================================================================

CREATE INDEX idx_users_provider_provider_id ON users(provider, provider_id);
CREATE INDEX idx_users_email ON users(email);
