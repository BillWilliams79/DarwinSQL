-- 064_add_machines.sql
--
-- Req #2943: `machines` entity — track WHICH machine ran each swarm_session,
-- swarm_start, and dev_server claim.
--
-- Two machines now run Darwin swarm work (Mac mini / iTerm launch path and the
-- WSL box / tmux launch path) with more possible. Nothing recorded which
-- machine a session/start/dev-server ran on. This migration introduces the
-- `machines` content table (auto-registered on first swarm activity) and stamps
-- the three execution tables with a nullable `machine_fk`.
--
-- Design bias — critical limited items only: a machine is a friendly name plus a
-- handful of shell-detectable facts (hostname/platform/arch/os_version/hw_model).
-- No browser/user-agent capture (sessions are CLI-side), no extended hardware
-- inventory (RAM/cores/GPU).
--
-- machines is a content-table baseline (memory/new-data-type-pattern.md): id,
-- title, description, closed, sort_order, creator_fk, create_ts/update_ts — PLUS
-- the auto-detected identity columns. NO category_fk (infrastructure entity, not
-- categorized). `hostname` is the auto-match key and is UNIQUE.
--
-- Nullable machine_fk by design: pre-feature rows stay NULL (no fabricated
-- attribution — same principle as swarm_sessions.legacy_secs). An OPTIONAL
-- one-time backfill (all pre-WSL history ran on the Mac mini) is shipped as a
-- commented-out statement at the bottom, applied by hand once the Mac's row
-- exists — never auto-applied.
--
-- dev_servers additionally SWAPS its port uniqueness: DROP the global uq_port,
-- ADD uq_machine_port(machine_fk, port). Ports are machine-local; the global
-- key made the two machines falsely contend for the 3000-3007 registry slots
-- even though the real ports don't conflict. Per-machine uniqueness gives each
-- machine the full pool. (MySQL treats NULLs as distinct in a UNIQUE key, so
-- legacy NULL-machine rows never contend with each other — acceptable since
-- dev_servers rows are transient.)
--
-- swarm_sessions/swarm_starts/dev_servers machine_fk FK: ON UPDATE CASCADE
-- ON DELETE RESTRICT (a machine with execution history cannot be hard-deleted;
-- retire it via the `closed` flag instead).
--
-- requirements table is OUT OF SCOPE — no requirements.machine_fk (can be added
-- later with the identical pattern if ever wanted).

-- ---------------------------------------------------------------------------
-- New table: machines
-- ---------------------------------------------------------------------------
CREATE TABLE machines (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(256) NOT NULL,           -- user-supplied friendly name; auto-registration seeds it with hostname
    description  TEXT         NULL,
    hostname     VARCHAR(128) NOT NULL,           -- auto-detected; the auto-match key; UNIQUE
    platform     VARCHAR(16)  NOT NULL,           -- darwin | wsl | linux (auto-detected)
    arch         VARCHAR(16)  NOT NULL,           -- arm64 | x86_64 (auto-detected)
    os_version   VARCHAR(64)  NULL,               -- auto: sw_vers on macOS; /etc/os-release PRETTY_NAME on Linux/WSL
    hw_model     VARCHAR(64)  NULL,               -- auto best-effort: `sysctl -n hw.model` on macOS (e.g. "Mac16,11");
                                                  -- hostnamectl "Hardware Model" or /proc/cpuinfo fallback on WSL; NULL when unavailable
    last_seen_at TIMESTAMP    NULL,               -- auto-updated on each identity resolution
    closed       TINYINT(1)   NOT NULL DEFAULT 0, -- retire a machine
    sort_order   SMALLINT     NULL,
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_machines_hostname (hostname),
    CONSTRAINT fk_machines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- machine_fk on the three execution tables (nullable; FK RESTRICT)
-- ---------------------------------------------------------------------------
ALTER TABLE swarm_sessions
    ADD COLUMN machine_fk INT NULL AFTER worktree_path,
    ADD CONSTRAINT fk_swarm_sessions_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE swarm_starts
    ADD COLUMN machine_fk INT NULL AFTER session_count,
    ADD CONSTRAINT fk_swarm_starts_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- dev_servers: add machine_fk AND swap the port uniqueness to per-machine.
ALTER TABLE dev_servers
    ADD COLUMN machine_fk INT NULL AFTER session_fk,
    ADD CONSTRAINT fk_dev_servers_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    DROP KEY uq_port,
    ADD UNIQUE KEY uq_machine_port (machine_fk, port);

-- ---------------------------------------------------------------------------
-- OPTIONAL one-time backfill (NOT auto-applied — user decision at review time)
-- ---------------------------------------------------------------------------
-- All pre-WSL swarm history ran on the Mac mini. Once the Mac's machines row
-- exists (auto-registered on the first post-deploy swarm launch, or inserted by
-- hand), a one-time UPDATE can attribute every NULL-machine execution row to it.
-- Replace <MAC_ID> with the Mac's machines.id and run by hand if desired:
--
--   UPDATE swarm_sessions SET machine_fk = <MAC_ID> WHERE machine_fk IS NULL;
--   UPDATE swarm_starts    SET machine_fk = <MAC_ID> WHERE machine_fk IS NULL;
--   -- dev_servers rows are transient; backfill is pointless there.
