CREATE SEQUENCE article_seq START WITH 1 INCREMENT BY 1;

CREATE SEQUENCE keyword_seq START WITH 1 INCREMENT BY 1;

CREATE SEQUENCE sub_seq START WITH 1 INCREMENT BY 1;

CREATE SEQUENCE trend_seq START WITH 1 INCREMENT BY 1;

CREATE SEQUENCE user_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE article_keywords
(
    id         NUMBER(38, 0) NOT NULL,
    article_id NUMBER(38, 0) NOT NULL,
    keyword    VARCHAR2(255) NOT NULL,
    weight     INTEGER       NOT NULL,
    created_at TIMESTAMP,
    CONSTRAINT pk_article_keywords PRIMARY KEY (id)
);

CREATE TABLE articles
(
    id           NUMBER(38, 0)  NOT NULL,
    title        VARCHAR2(1000) NOT NULL,
    summary      CLOB           NOT NULL,
    source_url   VARCHAR2(1000) NOT NULL,
    source       VARCHAR2(255)  NOT NULL,
    category     VARCHAR2(255)  NOT NULL,
    published_at TIMESTAMP,
    crawled_at   TIMESTAMP,
    CONSTRAINT pk_articles PRIMARY KEY (id)
);

CREATE TABLE subscriptions
(
    id         NUMBER(38, 0) NOT NULL,
    user_id    NUMBER(38, 0) NOT NULL,
    keyword    VARCHAR2(255) NOT NULL,
    created_at TIMESTAMP,
    CONSTRAINT pk_subscriptions PRIMARY KEY (id)
);

CREATE TABLE trend_metrics
(
    id             NUMBER(38, 0) NOT NULL,
    keyword        VARCHAR2(100) NOT NULL,
    category       VARCHAR2(100) NOT NULL,
    mention_count  INTEGER       NOT NULL,
    velocity_score FLOAT         NOT NULL,
    hotness_score  FLOAT         NOT NULL,
    updated_at     TIMESTAMP     NOT NULL,
    CONSTRAINT pk_trend_metrics PRIMARY KEY (id)
);

CREATE TABLE users
(
    id              NUMBER(38, 0) NOT NULL,
    provider        VARCHAR2(255),
    provider_id     VARCHAR2(255),
    email           VARCHAR2(255),
    role            VARCHAR2(255),
    discord_user_id VARCHAR2(255),
    username        VARCHAR2(255),
    created_at      TIMESTAMP,
    CONSTRAINT pk_users PRIMARY KEY (id)
);

ALTER TABLE articles
    ADD CONSTRAINT uc_articles_source_url UNIQUE (source_url);

ALTER TABLE users
    ADD CONSTRAINT uc_users_discord_user UNIQUE (discord_user_id);

ALTER TABLE article_keywords
    ADD CONSTRAINT FK_ARTICLE_KEYWORDS_ON_ARTICLE FOREIGN KEY (article_id) REFERENCES articles (id);

ALTER TABLE subscriptions
    ADD CONSTRAINT FK_SUBSCRIPTIONS_ON_USER FOREIGN KEY (user_id) REFERENCES users (id);