-- 066_add_requirement_machine.sql
--
-- Req #2978: pin a requirement to a specific machine.
--
-- Req #2943 (migration 064) introduced the `machines` entity and stamped
-- swarm_sessions / swarm_starts / dev_servers with a nullable `machine_fk`
-- recording WHERE each execution ran. It deliberately scoped `requirements`
-- out. This migration is that follow-up: `requirements.machine_fk` records
-- where a requirement is ALLOWED to run.
--
-- Semantics — NULL = "Any":
--   NULL          → the requirement may be launched on any machine (the default)
--   <machines.id> → the requirement is pinned; /swarm-start will only launch it
--                   on that machine, and refuses an explicit launch elsewhere.
--
-- No backfill. `NULL DEFAULT NULL` means every pre-existing requirement is "Any"
-- the moment this runs, which is the correct default — the handful that need a
-- pin are set by hand on the requirement detail page afterward. This is
-- deliberately unlike 064's commented-out execution-history backfill: that one
-- attributed the PAST (where work actually ran), this one constrains the FUTURE
-- (where work is allowed to run), and nothing in the existing data implies a
-- constraint the user never expressed.
--
-- FK matches the 064 convention exactly: ON UPDATE CASCADE ON DELETE RESTRICT.
-- A machine referenced by a requirement therefore cannot be hard-deleted —
-- retire it via `closed = 1` instead. (The MCP `delete_machine` guard message
-- names `requirements` alongside the three execution tables as of this req.)

ALTER TABLE requirements
    ADD COLUMN machine_fk INT NULL DEFAULT NULL AFTER effort,
    ADD CONSTRAINT fk_requirements_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;
