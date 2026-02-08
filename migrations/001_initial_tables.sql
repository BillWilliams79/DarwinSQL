-- Migration 001: Initial table creation
-- Creates: profiles, domains, areas, tasks
-- Note: profiles.id was originally INT AUTO_INCREMENT; changed in migration 004

USE darwin;

CREATE TABLE IF NOT EXISTS profiles (
    PRIMARY KEY (id),
    id              INT             NOT NULL AUTO_INCREMENT UNIQUE,
    name            VARCHAR(256)    NOT NULL,
    email           VARCHAR(256)    NOT NULL,
    subject         VARCHAR(64)     NOT NULL,
    userName        VARCHAR(256)    NOT NULL,
    region          VARCHAR(128)    NOT NULL,
    userPoolId      VARCHAR(128)    NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS domains (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT UNIQUE,
    domain_name     VARCHAR(32)     NOT NULL,
    creator_fk      INT             NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS areas (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT UNIQUE,
    area_name       VARCHAR(32)     NOT NULL,
    domain_fk       INT             NULL,
    creator_fk      INT             NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (domain_fk)
        REFERENCES domains (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT UNIQUE,
    priority        BOOLEAN         NOT NULL,
    done            BOOLEAN         NOT NULL,
    description     VARCHAR(256)    NOT NULL,
    area_fk         INT             NULL,
    creator_fk      INT             NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    done_ts         TIMESTAMP       NULL,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (area_fk)
        REFERENCES areas (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
