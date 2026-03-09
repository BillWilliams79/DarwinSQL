-- 014_create_priority_card_order.sql
-- Separate table for Priority Card hand-sort order.
-- Only contains rows for tasks that are actively hand-sorted in a priority card.
-- Rows are deleted when tasks are de-prioritized, marked done, or deleted.
CREATE TABLE IF NOT EXISTS priority_card_order (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    domain_id  INT      NOT NULL,
    task_id    INT      NOT NULL,
    sort_order SMALLINT NOT NULL,
    UNIQUE KEY uq_domain_task (domain_id, task_id)
);
