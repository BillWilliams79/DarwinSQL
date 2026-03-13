-- Migration 018: Fix categories sort_mode default from 'priority' to 'hand'
-- The categories table (created in migration 016) set sort_mode default to 'priority',
-- but the CategoryCard UI only supports 'hand' and 'created' sort modes.
-- Migration 013 renamed existing 'priority' rows to 'created' but did not change the column default.
-- Any new category created after migration 016 gets sort_mode='priority', causing no sort
-- option to appear selected in the three-dot menu.

-- Fix existing rows with invalid 'priority' sort_mode
UPDATE categories SET sort_mode = 'hand' WHERE sort_mode = 'priority';

-- Fix column default so future INSERTs without explicit sort_mode get 'hand'
ALTER TABLE categories ALTER COLUMN sort_mode SET DEFAULT 'hand';
