-- Migration 019: Change recurring_tasks.accumulate default from 1 (stack) to 0 (replace)
-- New recurring task definitions now default to replace mode (overwrite unfinished tasks)
-- rather than stack mode (accumulate tasks regardless of prior completion status).

ALTER TABLE recurring_tasks
    MODIFY COLUMN accumulate TINYINT(1) NOT NULL DEFAULT 0;
