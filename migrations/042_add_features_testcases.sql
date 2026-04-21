-- 042_add_features_testcases.sql
--
-- Req #2380 Phase 1: add the features + test_cases + feature_test_cases
-- tables for the Swarm Features & Test Cases registry.
--
-- features           — behavioral specifications (title + markdown description
--                      + feature_status draft|active|deprecated + category_fk)
-- test_cases         — verification procedures (title + preconditions + steps
--                      + expected + test_type manual|automated|hybrid + tags
--                      + category_fk). title is also the authoritative automation
--                      traceability key (Playwright describe/it names match).
-- feature_test_cases — junction, many-to-many. Composite PK, no id column.
--
-- FK policy:
--   category_fk → categories(id)  ON DELETE RESTRICT  (mirrors migration 041)
--   creator_fk  → profiles(id)    ON DELETE CASCADE
--   junction both sides           ON DELETE CASCADE
--
-- No schema-level CHECK constraints on the enum-style columns — Darwin validates
-- in the application layer (MCP + Lambda-Rest).

CREATE TABLE features (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NOT NULL,
    feature_status  VARCHAR(16)     NOT NULL DEFAULT 'draft',   -- draft|active|deprecated
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_features_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_features_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_cases (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    preconditions   TEXT            NULL,
    steps           TEXT            NOT NULL,
    expected        TEXT            NOT NULL,
    test_type       VARCHAR(16)     NOT NULL DEFAULT 'manual',  -- manual|automated|hybrid
    tags            VARCHAR(512)    NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_cases_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_cases_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE feature_test_cases (
    feature_fk      INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    PRIMARY KEY (feature_fk, test_case_fk),
    CONSTRAINT fk_ftc_feature
        FOREIGN KEY (feature_fk) REFERENCES features (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ftc_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
