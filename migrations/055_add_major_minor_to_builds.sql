-- 055_add_major_minor_to_builds.sql
--
-- Req #2720: Store major/minor version directly on each build row.
--
-- Previously, a build's M.m was inherited at render time from the owning
-- branch's (major, minor). This is wrong for main: main has ONE (major,
-- minor) row but lived through multiple M.m eras (e.g. 5.0 -> 5.1 -> 5.2
-- as releases were cut), so historical main builds displayed with main's
-- CURRENT M.m, which is wrong. Storing M.m per build eliminates the
-- "look back" entirely.
--
-- Default 0 is a safe placeholder; the two-phase backfill below stamps
-- every existing row with the correct value.

ALTER TABLE builds
    ADD COLUMN major INT NOT NULL DEFAULT 0 AFTER branch_number,
    ADD COLUMN minor INT NOT NULL DEFAULT 0 AFTER major;

-- Phase 1: ALL builds — inherit directly from owning branch M.m.
-- Correct for every non-trunk build. For trunk builds this gives the FIRST
-- era's M.m (since branch.major/minor stores the initial era); Phase 2
-- corrects trunk builds that belong to later eras.
UPDATE builds b
    JOIN branches br ON b.branch_fk = br.id
SET b.major = br.major,
    b.minor = br.minor;

-- Phase 2: trunk builds — fix main-branch builds whose M.m varies by era.
-- Each release branch cut from trunk advances trunk's minor by 1 (§4.2).
-- MySQL can't UPDATE a table that's referenced in a subquery, so we stage
-- the correct values in a temp table first.
CREATE TEMPORARY TABLE _trunk_era_counts AS
SELECT tb.id AS build_id,
       br.minor + (
           SELECT COUNT(*)
           FROM branches rel_br
           JOIN builds parent_b ON rel_br.parent_build_fk = parent_b.id
           WHERE rel_br.project_fk = bp.id
             AND rel_br.branch_type = 'release'
             AND rel_br.id != bp.trunk_branch_fk
             AND parent_b.branch_fk = bp.trunk_branch_fk
             AND parent_b.position < tb.position
       ) AS computed_minor
FROM builds tb
JOIN branches br ON tb.branch_fk = br.id
JOIN build_projects bp ON br.project_fk = bp.id
WHERE bp.trunk_branch_fk = tb.branch_fk;

UPDATE builds b
    JOIN _trunk_era_counts t ON b.id = t.build_id
SET b.minor = t.computed_minor;

DROP TEMPORARY TABLE _trunk_era_counts;
