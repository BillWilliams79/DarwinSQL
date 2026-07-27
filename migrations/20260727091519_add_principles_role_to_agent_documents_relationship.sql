-- 20260727091519_add_principles_role_to_agent_documents_relationship.sql
--
-- Req #3129: give every agent ONE guiding-principles document, identified by a
-- role on the existing agent_documents link rather than by a new column or table.
--
-- PROBLEM.  Nothing in the data marks which of an agent's documents carries its
--           guiding principles, so nothing can load it first or render it apart
--           from the rest. In practice the eleven `*-architect-charter.md` files
--           already ARE that document -- req #3129's audit found 54 of 78
--           instruction rows were verbatim restatements of them -- but that
--           status lives only in a naming convention, which no query can read.
--
-- SHAPE.    One new role in the `relationship` SET, plus a uniqueness rule that
--           is the MIRROR IMAGE of the existing owner rule:
--
--             uq_agent_documents_owner       one 'owned' link per DOCUMENT
--             uq_agent_documents_principles  one 'principles' link per AGENT
--
--           Hence the new virtual column keys on `agent_fk`, NOT `document_fk`.
--           Copying the owner rule verbatim would have let one agent hold many
--           principles documents while forbidding two agents from each having
--           their own -- exactly backwards. MySQL has no partial index, so the
--           same VIRTUAL-generated-column-plus-UNIQUE trick applies: the column
--           is NULL unless the SET contains 'principles', and NULLs are distinct
--           in a MySQL UNIQUE key, so unlimited non-principles links coexist.
--
--           Why not an `agents.principles` TEXT column? It would be editable in
--           the UI but would break the standing rule that `agents` stays narrow
--           and all growth lands in instruction/document ROWS -- and it would
--           strand the content outside git, losing PR review of doctrine.
--           Tagging a document keeps the file, its history, and its review, and
--           the UI already knows how to render and link a document.
--
--           ORDER MATTERS BELOW: the SET must accept 'principles' before any row
--           can carry it, and the generated column's expression references the
--           SET, so the MODIFY runs first.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands -- the
--           only difference is the trailing database name, so read it twice:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260727091519_add_principles_role_to_agent_documents_relationship.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260727091519_add_principles_role_to_agent_documents_relationship.sql darwin
--
--           The production command above requires
--           `bash scripts/db/rds-snapshot.sh 20260727091519` to report status=ok
--           first. See memory/database.md § Schema Migration Workflow.
--
--           NOTE: agent_documents is a PRODUCTION table -- the registry daemon
--           runs with DB_NAME=darwin -- so unlike most Darwin features this one
--           is not exercised by real data until the production apply lands.
--
-- Migration id 20260727091519 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

-- 1. Widen the SET so a link may carry the new role.
--    'principles' is listed FIRST: it is the highest-precedence role, and the
--    services layer ranks roles in this same declared order.
ALTER TABLE agent_documents
    MODIFY COLUMN relationship
        SET('principles','owned','curated','autoload','referenced')
        NOT NULL DEFAULT 'referenced';

-- 2. One principles document per AGENT, enforced the way the one-owner rule is.
--    Guarded on INFORMATION_SCHEMA so a re-run is a no-op rather than an error
--    (ADD COLUMN is not idempotent on its own).
SET @col_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'agent_documents'
      AND COLUMN_NAME  = 'principles_agent_fk'
);

SET @ddl := IF(@col_exists = 0,
    'ALTER TABLE agent_documents
        ADD COLUMN principles_agent_fk INT
            AS (IF(FIND_IN_SET(''principles'', relationship) > 0, agent_fk, NULL)) VIRTUAL,
        ADD UNIQUE KEY uq_agent_documents_principles (principles_agent_fk)',
    'SELECT ''principles_agent_fk already present - skipping'' AS note');

PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
