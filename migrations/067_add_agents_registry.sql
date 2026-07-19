-- 067_add_agents_registry.sql
--
-- Req #2997: Architect + Architecture Document data type (ownership registry).
--
-- PROBLEM. The 11 architect agents under `.claude/agents/` each carry their
-- entire brain as prose inside a single .md file. Nothing records WHO owns WHICH
-- document: an ownership survey (req #2982) found 6 of 11 agents with explicit
-- "Owned files" sections, 5 with ownership implied only, 2 stale entries
-- (cognito-config.md, tasks-architecture.md), and the req #2982 HTML docs
-- unowned entirely. Ownership that lives only in prose drifts silently.
--
-- SHAPE. Agent .md files become thin human-readable CHARTER STUBS; the durable
-- knowledge moves into these five tables and is read at agent boot through a
-- single MCP call (darwin://agents/<Agent Name>). The DB is canon; stub
-- frontmatter is a mirror reconciled at session boundaries by
-- scripts/swarm/reconcile-agent-stubs.sh (the harness cannot query MCP at spawn
-- time, so model/effort/description must physically exist in the file).
--
-- Every table here is a shape Darwin already has — flat content tables plus
-- plain junctions (memory/new-data-type-pattern.md). Deliberately NOT a generic
-- section/attribute store: an earlier `agent_sections` design was considered and
-- REJECTED during design (see req #2997 history). Long or complex content
-- belongs in an architecture document — a groomable md/html file — not in DB
-- prose. Fields edited in Darwin's UI are short by nature.
--
-- PRODUCTION table (not darwin_dev-only). Unlike the build-visualizer tables
-- (migration 057), the agent registry is a first-class production concern: the
-- MCP daemon runs with DB_NAME=darwin and every agent boot reads through it.
--
-- NO category_fk on any table. These are infrastructure entities describing the
-- tooling itself, not user-categorized content — same call as `machines`
-- (migration 064).
--
-- Phase 1 seeds ONE agent end-to-end (aws-architect) to prove the loading path.
-- The remaining 10 agents are req #2998.

-- ---------------------------------------------------------------------------
-- agents — one row per architect agent.
--
-- `name` is the MCP lookup key and matches the H1 in the charter stub
-- ("AWS Architect"); `file_name` is the stub's basename ("aws-architect.md").
-- Both are UNIQUE so either can resolve an agent, and neither can silently
-- duplicate.
--
-- ai_model/effort are the STANDARD HEADER PIN: every architect defaults to
-- opus[1m] / high, replacing the stale per-agent `claude-opus-4-6` pins. These
-- are the values a reconcile writes into stub frontmatter. Precedence at spawn:
-- an explicit session / swarm / requirement setting overrides; absent an
-- override, the pin is what you get.
--
-- ai_model is VARCHAR, NOT an ENUM — it holds a RESOLVED model id ('opus[1m]')
-- rather than one of Darwin's haiku|sonnet|opus|fable family names, and resolved
-- ids change with every model release. An ENUM would demand a migration per
-- release. `effort` IS constrained (low|medium|high|xhigh|ultracode is a stable,
-- Darwin-owned vocabulary — same set as requirements.effort, migration 063).
-- ---------------------------------------------------------------------------
CREATE TABLE agents (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(128) NOT NULL,                    -- human-readable, e.g. "AWS Architect"; MCP key; UNIQUE
    file_name   VARCHAR(128) NOT NULL,                    -- stub basename, e.g. "aws-architect.md"; UNIQUE
    overview    TEXT         NULL,                        -- short delegation trigger; mirrored to stub `description`
    ai_model    VARCHAR(32)  NOT NULL DEFAULT 'opus[1m]', -- resolved model id (see note above)
    effort      VARCHAR(16)  NOT NULL DEFAULT 'high',     -- low|medium|high|xhigh|ultracode
    location    VARCHAR(512) NULL,                        -- repo-relative stub path, e.g. ".claude/agents/aws-architect.md"
    closed      TINYINT(1)   NOT NULL DEFAULT 0,          -- retire an agent without deleting its history
    sort_order  SMALLINT     NULL,
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_agents_name (name),
    UNIQUE KEY uq_agents_file_name (file_name),
    CONSTRAINT fk_agents_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- instructions — reusable named blocks of BINDING text.
--
-- Its own data type precisely so one row can serve many agents: the grooming
-- duty ("re-groom the owned document whenever its spec changes, so it never
-- drifts") is ONE row linked to all 11 agents. Edit it once, every architect
-- picks up the change at next boot. Per-agent instructions are ordinary rows
-- linked to exactly one agent.
-- ---------------------------------------------------------------------------
CREATE TABLE instructions (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(256) NOT NULL,   -- UNIQUE; the upsert key for idempotent seeding
    content     TEXT         NOT NULL,   -- the binding text itself
    closed      TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order  SMALLINT     NULL,
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_instructions_name (name),
    CONSTRAINT fk_instructions_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- agent_instructions — which instructions bind which agent, and in what order.
--
-- CASCADE both sides: an unlinked instruction is meaningless, and deleting an
-- agent should not strand junction rows. `sort_order` drives the load order the
-- charter stub promises ("sections by sort_order").
-- ---------------------------------------------------------------------------
CREATE TABLE agent_instructions (
    agent_fk        INT      NOT NULL,
    instruction_fk  INT      NOT NULL,
    sort_order      SMALLINT NULL,
    PRIMARY KEY (agent_fk, instruction_fk),
    CONSTRAINT fk_ai_agent
        FOREIGN KEY (agent_fk) REFERENCES agents (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ai_instruction
        FOREIGN KEY (instruction_fk) REFERENCES instructions (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- architecture_documents — THE ONE registry of documents.
--
-- Exactly one documents table exists. `agent_documents` below is a junction of
-- RELATIONSHIPS, not a second list of documents.
--
-- `location` is repo-relative (e.g. "memory/aws-cost.md") — the path an agent
-- Reads at boot. `url` is the clickable form for the Phase 2 UI: a GitHub blob
-- link for markdown, a site path for html. Both are nullable because a document
-- may be registered before either is settled.
-- ---------------------------------------------------------------------------
CREATE TABLE architecture_documents (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(256) NOT NULL,   -- UNIQUE; the upsert key for idempotent seeding
    doc_type    VARCHAR(16)  NOT NULL DEFAULT 'markdown',  -- markdown|html|text
    location    VARCHAR(512) NULL,       -- repo-relative path the agent Reads
    url         VARCHAR(1024) NULL,      -- clickable link (GitHub blob / site path)
    closed      TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order  SMALLINT     NULL,
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_architecture_documents_name (name),
    CONSTRAINT fk_architecture_documents_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- agent_documents — the many-to-many relationship rows.
--
-- relationship semantics (drives what the agent does with the file at boot):
--   owned          responsible party; reads IN FULL before starting a task
--   groomed        keeps it current; reads IN FULL before starting a task
--   referenced     consults on demand — NOT auto-loaded
--   design_language  visual/structural rules it must honor
--   guardian       a standing duty to verify (e.g. schema-of-record parity)
--
-- "AT MOST ONE 'owned' PER DOCUMENT" is enforced BY THE DATABASE, not by prose.
-- MySQL has no partial/filtered unique index, so `owned_document_fk` is a
-- VIRTUAL generated column that equals document_fk only on an 'owned' row and is
-- NULL otherwise; a UNIQUE key over it does the work. MySQL treats NULLs as
-- distinct in a UNIQUE key, so unlimited groomed/referenced/design_language/
-- guardian links coexist freely while a SECOND 'owned' link on the same document
-- raises IntegrityError. VIRTUAL (not STORED): the value is computed on read and
-- costs no row storage; MySQL 8 indexes virtual columns natively.
--
-- This is the rule the whole requirement exists to enforce — one named
-- responsible architect per document. Cross-architect polish remains allowed
-- (an architect may polish another's document when certain the responsible one
-- will not), but that is a fallback, not a second ownership claim.
-- ---------------------------------------------------------------------------
CREATE TABLE agent_documents (
    agent_fk           INT          NOT NULL,
    document_fk        INT          NOT NULL,
    relationship       VARCHAR(24)  NOT NULL DEFAULT 'referenced',  -- owned|groomed|referenced|design_language|guardian
    notes              VARCHAR(512) NULL,      -- per-link caveats (e.g. "vendored copy — upstream is Topology/")
    sort_order         SMALLINT     NULL,
    owned_document_fk  INT          AS (IF(relationship = 'owned', document_fk, NULL)) VIRTUAL,
    PRIMARY KEY (agent_fk, document_fk),
    UNIQUE KEY uq_agent_documents_owner (owned_document_fk),
    CONSTRAINT fk_ad_agent
        FOREIGN KEY (agent_fk) REFERENCES agents (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ad_document
        FOREIGN KEY (document_fk) REFERENCES architecture_documents (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
