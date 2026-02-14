-- Migration 007: Add sort_order column to tasks table
-- Supports hand-sort mode: user-defined task ordering within area cards
ALTER TABLE tasks ADD COLUMN sort_order SMALLINT NULL;
