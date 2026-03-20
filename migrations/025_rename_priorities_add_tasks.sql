-- Migration 025: Rename "Priorities" category to "Swarm", add "Tasks" category,
-- re-shuffle sort_orders, reassign closed priorities to correct category.
--
-- Target state:
--   ID 1   → Swarm           (sort_order 0)
--   NEW    → Tasks           (sort_order 1)
--   ID 577 → Mapping         (sort_order 2)
--   ID 23  → Dead Letter File (sort_order 3)
--
-- Apply to darwin_dev first, then darwin production.

-- 1. Rename "Priorities" → "Swarm"
UPDATE categories
SET category_name = 'Swarm'
WHERE category_name = 'Priorities';

-- 2. Create "Tasks" category (idempotent — skip if already exists)
INSERT INTO categories (category_name, project_fk, creator_fk, sort_order, sort_mode, closed)
SELECT 'Tasks', 1, '37df7531-000d-4470-8be4-1792d8261f69', 1, 'hand', 0
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM categories
    WHERE category_name = 'Tasks'
    AND creator_fk = '37df7531-000d-4470-8be4-1792d8261f69'
);

-- 3. Bump sort_orders: Mapping → 2, Dead Letter File → 3
UPDATE categories SET sort_order = 2 WHERE id = 577;
UPDATE categories SET sort_order = 3 WHERE id = 23;

-- 4. Reassign closed priorities from Swarm (category 1) to Tasks category.
-- Uses a subquery to resolve the Tasks category ID dynamically.
-- Only moves the specific 47 items identified as app features, not swarm/infra work.
UPDATE priorities
SET category_fk = (
    SELECT id FROM categories
    WHERE category_name = 'Tasks'
    AND creator_fk = '37df7531-000d-4470-8be4-1792d8261f69'
    LIMIT 1
)
WHERE id IN (
    8, 11, 14, 65, 257, 258, 260, 261, 262, 372,
    448, 505, 512, 604, 605, 629, 643, 664, 698, 789,
    817, 824, 863, 864, 968, 983, 984, 1019, 1020, 1021,
    1220, 1222, 1295, 1298, 1300, 1301, 1302, 1303, 1433,
    1460, 1503, 1505, 1506, 1559, 1565, 1602, 1614
);
