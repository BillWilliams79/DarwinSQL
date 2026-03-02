-- Migration 010: Add dev_servers table for port coordination
-- Tracks which Claude session owns which dev server port

CREATE TABLE IF NOT EXISTS dev_servers (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    port            SMALLINT        NOT NULL,
    pid             INT             NOT NULL,
    workspace_path  VARCHAR(512)    NOT NULL,
    session_fk      INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_port (port),
    FOREIGN KEY (creator_fk) REFERENCES profiles (id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (session_fk) REFERENCES swarm_sessions (id) ON UPDATE CASCADE ON DELETE SET NULL
);
