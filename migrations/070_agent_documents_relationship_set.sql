-- 070_agent_documents_relationship_set.sql
--
-- Req #3012: Refactor Agent Harness — independent document relationship tags.
--
-- PROBLEM. `agent_documents.relationship` was a single VARCHAR value per link
-- (owned | groomed | referenced | design_language | guardian), and `autoload`
-- was DERIVED (owned+groomed). That made the roles dependent: a document could
-- not be `owned` AND separately `autoload`, and `groomed` was the outdated term
-- for keeping a document current.
--
-- SHAPE. `relationship` becomes a MySQL SET so one link carries one or more
-- INDEPENDENT roles. The role vocabulary is collapsed and renamed:
--   groomed                -> curated        (kept-current duty; new vocabulary)
--   design_language        -> referenced     (folded away)
--   guardian               -> referenced     (folded away)
--   autoload               -> a STORED role  (no longer derived from owned+groomed)
-- Final vocabulary: owned | curated | autoload | referenced.
--
-- BEHAVIOUR PRESERVED. Every document that autoloaded before (the old owned OR
-- groomed set) gets an explicit `autoload` role here, so nothing changes about
-- what an agent reads at boot until an owner later prunes it. `notes`/`sort_order`
-- stay per-link (one row per agent+document); the one-`owned`-per-document rule
-- is preserved via the same VIRTUAL generated column + UNIQUE key, now testing
-- membership with FIND_IN_SET instead of string equality.
--
-- ORDERING IS LOAD-BEARING. The old virtual column keys off `relationship='owned'`
-- (exact match). Appending ',autoload' to an owned row would make that exact
-- match fail and silently drop the owner from the unique key. So we DROP the
-- owner key + virtual column BEFORE mutating owned/curated rows, then rebuild the
-- virtual column with FIND_IN_SET after the SET conversion.

-- 1. Rename single-value roles while still VARCHAR (virtual column stays correct:
--    curated/referenced != 'owned', owned rows untouched).
UPDATE agent_documents SET relationship = 'curated'    WHERE relationship = 'groomed';
UPDATE agent_documents SET relationship = 'referenced' WHERE relationship IN ('design_language', 'guardian');

-- 2. Drop the owner unique key + virtual column so we can (a) mutate owned rows
--    without the exact-match column mislabelling them and (b) alter the column type.
ALTER TABLE agent_documents DROP KEY uq_agent_documents_owner;
ALTER TABLE agent_documents DROP COLUMN owned_document_fk;

-- 3. Give every currently-autoloaded link (owned or curated) an explicit autoload
--    role. VARCHAR(24) holds "owned,autoload" (14) / "curated,autoload" (16) fine.
UPDATE agent_documents SET relationship = CONCAT(relationship, ',autoload')
    WHERE relationship IN ('owned', 'curated');

-- 4. Convert to a SET. MySQL parses each comma-separated string into set members;
--    all existing values ("owned,autoload", "curated,autoload", "referenced") are
--    valid members, so the conversion is lossless.
ALTER TABLE agent_documents
    MODIFY COLUMN relationship SET('owned','curated','autoload','referenced')
    NOT NULL DEFAULT 'referenced'
    COMMENT 'independent roles: owned|curated|autoload|referenced (req #3012)';

-- 5. Rebuild the one-owner virtual column + unique key against SET membership.
ALTER TABLE agent_documents
    ADD COLUMN owned_document_fk INT
        AS (IF(FIND_IN_SET('owned', relationship) > 0, document_fk, NULL)) VIRTUAL;
ALTER TABLE agent_documents
    ADD UNIQUE KEY uq_agent_documents_owner (owned_document_fk);

-- 6. Retire instructions renamed/replaced by req #3012. The two former common
--    rows are subsumed by the new `common-documents` instruction; the darwin
--    grooming row is renamed to `darwin-curating-does-not-transfer-ownership`.
--    All three are re-seeded (where still needed) by scripts/seed-agents-registry.py;
--    agent_instructions links cascade on delete.
DELETE FROM instructions
    WHERE name IN ('common-document-grooming-duty',
                   'common-load-owned-documents-first',
                   'darwin-grooming-does-not-transfer-ownership');
