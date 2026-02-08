-- Migration 006: Expand task description field
-- User request to allow longer task descriptions (256 -> 1024)

USE darwin;

ALTER TABLE tasks
MODIFY COLUMN description VARCHAR(1024) NOT NULL;
