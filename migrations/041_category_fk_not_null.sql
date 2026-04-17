-- 041_category_fk_not_null.sql
--
-- Enforce requirements.category_fk NOT NULL (req #2217). Three requirements
-- (#2191, #2195, #2196) became invisible in the UI because they had NULL
-- category_fk; lock the door so no future row can be uncategorized.
--
-- Because category_fk becomes NOT NULL, the old ON DELETE SET NULL FK action
-- is illegal. Re-create the FK with ON DELETE RESTRICT — deleting a category
-- with live requirements will now be rejected. darwin-mcp db.delete_category
-- catches the IntegrityError and surfaces a readable ValueError.
--
-- Pre-flight: 311 uncategorized E2E test artifacts were deleted from prod on
-- 2026-04-17 before this migration (all title LIKE 'e2e-%', creator was
-- e2e-test@test.invalid or e2e-worker-1@test.invalid). darwin_dev was
-- already clean.

-- Guard: abort if any NULL rows still exist.
SET @null_count = (SELECT COUNT(*) FROM requirements WHERE category_fk IS NULL);
SET @sql = IF(@null_count > 0,
    CONCAT('SIGNAL SQLSTATE ''45000'' SET MESSAGE_TEXT = ''migration 041 aborted: ',
           @null_count, ' requirements have NULL category_fk'''),
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Drop the existing unnamed FK (category_fk → categories.id). Look up by
-- column so we don't rely on MySQL's auto-generated constraint name.
SET @fk_name = (
    SELECT CONSTRAINT_NAME
      FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = 'requirements'
       AND COLUMN_NAME = 'category_fk'
       AND REFERENCED_TABLE_NAME = 'categories'
       AND REFERENCED_COLUMN_NAME = 'id'
     LIMIT 1
);
SET @sql = CONCAT('ALTER TABLE requirements DROP FOREIGN KEY ', @fk_name);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Flip column to NOT NULL.
ALTER TABLE requirements MODIFY COLUMN category_fk INT NOT NULL;

-- Re-add FK with a stable name and ON DELETE RESTRICT.
ALTER TABLE requirements
ADD CONSTRAINT fk_requirements_category
    FOREIGN KEY (category_fk)
    REFERENCES categories(id)
    ON UPDATE CASCADE
    ON DELETE RESTRICT;
