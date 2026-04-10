-- Rename "priorities" to "requirements" throughout the roadmap/swarm system.
-- Task-level priority (tasks.priority, recurring_tasks.priority, priority_card_order) is UNCHANGED.

-- 1. Rename tables
RENAME TABLE priorities TO requirements;
RENAME TABLE priority_sessions TO requirement_sessions;

-- 2. Rename columns
ALTER TABLE requirements CHANGE COLUMN priority_status requirement_status VARCHAR(16) NOT NULL DEFAULT 'idle';
ALTER TABLE requirement_sessions CHANGE COLUMN priority_fk requirement_fk INT NOT NULL;

-- 3. Migrate source_ref values in swarm_sessions
UPDATE swarm_sessions SET source_ref = CONCAT('requirement:', SUBSTRING(source_ref, 10))
WHERE source_ref LIKE 'priority:%';

-- 4. Update section comment (schema.sql only — not a DDL operation)
-- Section header: "Roadmap / priority tracking" → "Roadmap / requirement tracking"
