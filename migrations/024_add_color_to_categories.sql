-- Migration 024: Add color column to categories
-- Enables per-category color accents on Calendar priority events

ALTER TABLE categories ADD COLUMN color VARCHAR(9) NULL AFTER sort_mode;

-- Set category colors (Dead Letter File stays NULL — no accent)
UPDATE categories SET color = '#E63946' WHERE id = 1;    -- Swarm → red
UPDATE categories SET color = '#FFD60A' WHERE id = 845;  -- Tasks → yellow
UPDATE categories SET color = '#0077B6' WHERE id = 577;  -- Mapping → blue
