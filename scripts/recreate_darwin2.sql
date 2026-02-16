-- Recreate darwin2 test/dev tables from scratch
-- Mirrors schema.sql with '2' suffix on all table names and FK references
-- Idempotent: safe to run repeatedly to reset darwin2 to canonical state

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS tasks2, areas2, domains2, profiles2;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE profiles2 (
    id              VARCHAR(64)     NOT NULL PRIMARY KEY,
    name            VARCHAR(256)    NOT NULL,
    email           VARCHAR(256)    NOT NULL,
    subject         VARCHAR(64)     NOT NULL,
    userName        VARCHAR(256)    NOT NULL,
    region          VARCHAR(128)    NOT NULL,
    userPoolId      VARCHAR(128)    NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE domains2 (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    domain_name     VARCHAR(32)     NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT         NOT NULL DEFAULT 0,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles2 (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE areas2 (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    area_name       VARCHAR(32)     NOT NULL,
    domain_fk       INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT         NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    sort_mode       VARCHAR(8)      NOT NULL DEFAULT 'priority',
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles2 (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (domain_fk)
        REFERENCES domains2 (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE tasks2 (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    priority        BOOLEAN         NOT NULL,
    done            BOOLEAN         NOT NULL,
    description     VARCHAR(1024)   NOT NULL,
    area_fk         INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    done_ts         TIMESTAMP       NULL,
    sort_order      SMALLINT        NULL,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles2 (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (area_fk)
        REFERENCES areas2 (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
