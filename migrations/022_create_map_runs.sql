CREATE TABLE IF NOT EXISTS map_runs (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    run_id          INT             NOT NULL,
    map_route_fk    INT             NULL,
    activity_id     INT             NOT NULL,
    activity_name   VARCHAR(16)     NOT NULL,
    start_time      DATETIME        NOT NULL,
    run_time_sec    INT             NOT NULL,
    stopped_time_sec INT            NOT NULL DEFAULT 0,
    distance_mi     DECIMAL(6,1)    NOT NULL,
    ascent_ft       INT             NULL,
    descent_ft      INT             NULL,
    calories        INT             NULL,
    max_speed_mph   DECIMAL(5,1)    NULL,
    avg_speed_mph   DECIMAL(5,2)    NULL,
    notes           TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (map_route_fk)
        REFERENCES map_routes (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
