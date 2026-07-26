-- 073_agent_instructions_unique_slot.sql
--
-- Req #3075 — give `agent_instructions.sort_order` the per-agent uniqueness guard
-- it has never had. DML repair + DDL. Autonomy-granted 2026-07-25.
--
-- THE INVARIANT THIS ESTABLISHES
--
--   For one agent, at most one instruction may claim any given NUMBERED boot-load
--   slot. A NULL sort_order claims no slot and is deliberately unconstrained.
--
-- `agent_instructions` has PK (agent_fk, instruction_fk) and nothing else. Since
-- migration 072 its `sort_order` is the ONLY instruction ordering left in the
-- schema, and it is the boot load order — so two rows sharing a slot means an
-- agent loads its binding rules in arbitrary order between the colliding pair,
-- with no error, no warning, and a payload that still looks well-formed.
--
-- NOT HYPOTHETICAL. Measured on production `darwin` before writing this file:
--   agent_fk=5 (Darwin Architect), sort_order=1 held by instruction_fk 23 AND 84.
-- 111 junction rows, 0 NULLs, that one collision. `darwin_dev`: 90 rows, clean.
-- The req #3063 serialized membership queue was already live and did not prevent
-- it, because the collision did not arrive through that page. That is the whole
-- argument for putting the guard in the database instead of in a convention.
--
-- WHY A PLAIN UNIQUE KEY IS SAFE HERE — the three objections, answered
--
-- 1. "The DELETE-then-POST reorder transiently holds both rows at overlapping
--    values, so the re-POST would be rejected." It does not.
--    `Darwin/src/Agents/actions/instructionsApi.js::setAgentInstructionOrder`
--    DELETEs EVERY row in the write set first, then re-creates them all in ONE
--    array-body POST. No instant exists where two rows of one agent hold the same
--    numbered slot. Its rollback path re-posts the originals into slots the same
--    loop vacated. The path is already constraint-compliant.
--
--    darwin-mcp's `link_agent_instruction` WAS a single delete-then-post, which
--    this key would have made unable to express a reorder at all. It is changed in
--    the same requirement to the same delete-all-then-post-all shape: moving an
--    existing binding onto a slot held by another OPEN instruction now SWAPS the
--    two, and every other move onto an occupied slot is rejected by name.
--
-- 2. "It would force a 1..N renumber and collapse the bands." It would not.
--    UNIQUE forbids duplicates; it says nothing about density. The live banded
--    layout — per-agent rules at 1..N, the shared `common-*` rows together at
--    100+, the 4..99 gap kept free for extension — satisfies UNIQUE exactly as it
--    stands. `repairInstructionOrders` already emits a strictly-increasing,
--    duplicate-free, value-PRESERVING sequence and needs no change.
--
-- 3. "NULL is legal and MySQL UNIQUE permits multiple NULLs, so it doesn't cover
--    the unordered case." That is the correct SCOPE, not a gap. NULL means no slot
--    claimed. Forcing NOT NULL would invent a slot for a link that deliberately
--    has none and would break link_agent_instruction's COALESCE contract (req
--    #3049). Unnumbered links are ordered by a documented `id ASC` tie-break in
--    both readers.
--
-- WHY `agent_documents` DOES NOT GET THE SAME KEY
--
-- That sibling junction sorts by RELATIONSHIP RANK first and `sort_order` second,
-- so slot 1 in the `owned` group and slot 1 in the `referenced` group are
-- different positions and legitimately coexist — all 12 agents do exactly that
-- today (document 68 was bulk-linked at slot 1 alongside each agent's owned
-- document at slot 1). Its invariant would be
-- UNIQUE(agent_fk, relationship-rank, sort_order), which is a different question
-- and a different requirement. Bundling it in here would have silently renumbered
-- 12 agents' document lists.
--
-- STEP 1 — BAND-PRESERVING REPAIR
--
-- Generic, deterministic, and re-runnable (a no-op once no duplicates remain).
-- The rule mirrors `repairInstructionOrders`: keep good values, move only what
-- must move, never renumber a non-colliding row.
--
--   * Within each colliding (agent_fk, sort_order) group the LOWEST instruction_fk
--     KEEPS the slot — so the row a reader currently sees FIRST of the colliding
--     pair stays exactly where it is. The others necessarily move, and moving them
--     changes their reading position relative to the keeper: seeding 5,5,5 for one
--     agent repairs to 5,1,2, which reads as 21,22,20 rather than 20,21,22. That is
--     unavoidable — the whole point is that their old shared position was never
--     well-defined. Lowest-instruction_fk-wins is the tie-break BOTH readers land
--     on today, though for different reasons:
--     darwin-mcp's list_instructions_for_agent sorts explicitly by
--     (link_sort_order ASC NULLS LAST, id ASC); the Darwin UI's
--     instructionLinksByAgent does a STABLE sort on sort_order over rows arriving
--     in the junction's clustered-PK order (agent_fk, instruction_fk) — it has no
--     ORDER BY of its own, so its tie-break is emergent rather than declared.
--   * Every other row of that agent takes a slot from that agent's ascending list
--     of FREE slots (free = claimed by no pre-repair row of that agent), handed out
--     by a per-agent global ordinal so two different colliding groups can never be
--     assigned the same value.
--
-- On production that moves instruction 84 from slot 1 to slot 7 — the first free
-- slot in the Darwin Architect's per-agent band (1..6 occupied), leaving the
-- shared 100/101/102 band untouched.
--
-- RE-RUNNABILITY. Step 1 is idempotent — once no duplicate numbered slot remains,
-- `movers` is empty and it updates nothing. The FILE as a whole is not: a second
-- run dies at step 2 with 1061 (duplicate key name), which is the harmless shape.
--
-- The 1..1000 candidate range covers both bands with room to spare and stays
-- inside MySQL's default cte_max_recursion_depth of 1000. It cannot be exhausted
-- by any realistic data (production holds 111 junction rows in total), but be
-- clear about what happens if it ever were: an agent with no free slot ≤ 1000
-- loses its movers to the JOIN, they keep their duplicate values, and step 2 then
-- FAILS on those rows. Step 1 has already COMMITTED by then — autocommit, no
-- transactional DDL — so the database is left partly repaired rather than
-- untouched. Recovery is to widen the range and re-run step 1, which is safe
-- because step 1 is idempotent. The ALTER is the verification, not a rollback.

UPDATE agent_instructions ai
JOIN (
    WITH RECURSIVE nums (n) AS (
        SELECT 1
        UNION ALL
        SELECT n + 1 FROM nums WHERE n < 1000
    ),
    occupied AS (
        SELECT DISTINCT agent_fk, sort_order
          FROM agent_instructions
         WHERE sort_order IS NOT NULL
    ),
    movers AS (
        SELECT agent_fk,
               instruction_fk,
               ROW_NUMBER() OVER (PARTITION BY agent_fk
                                  ORDER BY sort_order, instruction_fk) AS pick
          FROM (
                SELECT agent_fk,
                       instruction_fk,
                       sort_order,
                       ROW_NUMBER() OVER (PARTITION BY agent_fk, sort_order
                                          ORDER BY instruction_fk) AS rn
                  FROM agent_instructions
                 WHERE sort_order IS NOT NULL
               ) ranked
         WHERE ranked.rn > 1
    ),
    free_slots AS (
        SELECT o.agent_fk,
               nums.n,
               ROW_NUMBER() OVER (PARTITION BY o.agent_fk ORDER BY nums.n) AS pick
          FROM (SELECT DISTINCT agent_fk FROM occupied) o
          CROSS JOIN nums
         WHERE NOT EXISTS (SELECT 1
                             FROM occupied x
                            WHERE x.agent_fk = o.agent_fk
                              AND x.sort_order = nums.n)
    )
    SELECT m.agent_fk, m.instruction_fk, f.n AS new_sort_order
      FROM movers m
      JOIN free_slots f
        ON f.agent_fk = m.agent_fk
       AND f.pick = m.pick
) repair
  ON repair.agent_fk = ai.agent_fk
 AND repair.instruction_fk = ai.instruction_fk
SET ai.sort_order = repair.new_sort_order;

-- STEP 2 — THE GUARD
--
-- Multi-NULL-permissive by MySQL's UNIQUE semantics, which is exactly the scope
-- argued above. This ALTER is also the repair's verification: it cannot succeed
-- while a duplicate numbered slot remains.

ALTER TABLE agent_instructions
    ADD UNIQUE KEY uq_agent_instructions_slot (agent_fk, sort_order);

-- ROLLBACK
--   ALTER TABLE agent_instructions DROP INDEX uq_agent_instructions_slot;
-- The repaired sort_order values are NOT restored by that drop and should not be
-- — they are the corrected state, not damage.
--
-- APPLY ORDER: darwin_dev first, verify, THEN production behind an RDS snapshot.
--
-- Deploy ordering vs. the frontend bundle is a NON-ISSUE here, unlike migration
-- 072. This file adds a key and rewrites at most a handful of sort_order values;
-- it removes no column and changes no result shape, so the currently-live bundle
-- keeps working unchanged either side of it.
--
-- Verification: expect an empty result (no duplicate numbered slot survives).
-- SELECT agent_fk, sort_order, COUNT(*) c
--   FROM agent_instructions
--  WHERE sort_order IS NOT NULL
--  GROUP BY agent_fk, sort_order
-- HAVING c > 1;
