-- Migration 017: Add recurring_tasks table and recurring_task_fk to tasks
-- recurring_tasks: stores user-defined recurring task templates
-- tasks.recurring_task_fk: traces which template generated each task instance

CREATE TABLE recurring_tasks (
    id               INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    description      VARCHAR(1024)   NOT NULL,
    recurrence       VARCHAR(16)     NOT NULL,
    anchor_date      DATE            NOT NULL,
    area_fk          INT             NOT NULL,
    priority         TINYINT(1)      NOT NULL DEFAULT 0,
    accumulate       TINYINT(1)      NOT NULL DEFAULT 1,
    insert_position  VARCHAR(8)      NOT NULL DEFAULT 'bottom',
    active           TINYINT(1)      NOT NULL DEFAULT 1,
    last_generated   DATE            NULL,
    creator_fk       VARCHAR(64)     NOT NULL,
    create_ts        TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts        TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (area_fk)
        REFERENCES areas (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

ALTER TABLE tasks
    ADD COLUMN recurring_task_fk INT NULL AFTER sort_order,
    ADD CONSTRAINT fk_tasks_recurring
        FOREIGN KEY (recurring_task_fk) REFERENCES recurring_tasks (id) ON DELETE SET NULL;
