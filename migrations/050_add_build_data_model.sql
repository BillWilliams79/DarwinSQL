-- 050_add_build_data_model.sql
--
-- Req #2606: SQL-backed Build Visualizer data model + Customer Release Events.
--
-- Canonical items: Project, Branch, Build, Customer, Release.
--
-- Trunk:
--   Whichever branch the project's `trunk_branch_fk` points at. That branch has
--   `branch_type='release'`, `parent_build_fk=NULL`. No boolean flag — the
--   FK link from the project IS the trunk-identity declaration.
--
-- Versioning (compute-once-at-creation, no segments, no walk at render):
--   * `branches.major` / `branches.minor` are STORED on the branch row at
--     creation time. Inherited from origin-build's branch for sub-branches;
--     set explicitly for trunk (project starter) and release branches (user
--     picks at dialog).
--   * `builds.build_number` (the B) is STORED on each build at creation time.
--     Trunk builds increment monotonically; sub-branch builds inherit the
--     FROZEN parent-trunk-build's B per design-guide §4.2.
--   * `builds.branch_number` (the b) is STORED on each build at creation time
--     using the reserved-range rules (0 for trunk, i+1 for release /
--     sample-release, ord1*1000+i+1 for csr, 6000+ord0*100+i+1 for hotfix,
--     7000+ord0*100+i+1 for development, 9000+ord0*100+i+1 for bootleg).
--   * Renderer formats `M.m.B.b` purely from stored values — no engine walk.
--   * The segment concept is DELETED. Each branch carries its own M.m
--     directly; there is no trunk-segment table or column.
--
-- Branch parentage:
--   A branch originates from a specific Build. `branches.parent_build_fk`
--   points at that build. The parent BRANCH is derivable:
--     SELECT branch_fk FROM builds WHERE id = branch.parent_build_fk
--   So there is NO `parent_branch_fk` column — single source of truth.
--   The trunk is the only branch with `parent_build_fk = NULL`.
--
-- No soft delete (`closed` removed from every new table per req #2606
-- directive). Project / branch / build deletion is hard delete via the
-- existing FK CASCADE chain.
--
-- FK policies:
--   build_projects.category_fk -> categories     RESTRICT
--   build_projects.trunk_branch_fk -> branches   SET NULL (deferred ALTER)
--   build_projects.creator_fk -> profiles        CASCADE
--   branches.project_fk -> build_projects        CASCADE
--   branches.parent_build_fk -> builds           SET NULL (deferred ALTER)
--   branches.creator_fk -> profiles              CASCADE
--   builds.branch_fk -> branches                 CASCADE
--   builds.creator_fk -> profiles                CASCADE
--   customer_releases.customer_fk -> customers   RESTRICT
--   customer_releases.build_fk -> builds         CASCADE
--   customer_releases.creator_fk -> profiles     CASCADE
--
-- Two deferred ALTERs handle the circular FKs:
--   branches.parent_build_fk        <-> builds.branch_fk
--   build_projects.trunk_branch_fk  <-> branches.project_fk

-- ----------------------------------------------------------------------------
-- 1. build_projects (without trunk_branch_fk — added by deferred ALTER below)
-- ----------------------------------------------------------------------------

CREATE TABLE build_projects (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    project_status  VARCHAR(16)     NOT NULL DEFAULT 'draft', -- draft|active|archived
    sort_order      SMALLINT        NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_build_projects_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_build_projects_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 2. branches (without parent_build_fk — added by deferred ALTER below)
-- ----------------------------------------------------------------------------

CREATE TABLE branches (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    project_fk          INT             NOT NULL,
    branch_type         VARCHAR(32)     NOT NULL, -- release|sample-release|hotfix|bootleg|csr|development
    name                TEXT            NULL,     -- multi-line allowed (\n stacks vertically)
    major               INT             NOT NULL, -- M.m stored on the branch (compute-once on create)
    minor               INT             NOT NULL,
    -- parent_build_fk INT NULL  added by deferred ALTER below
    side                VARCHAR(16)     NULL,     -- override REGISTRY default (above|below|center)
    row_order           INT             NULL,     -- override REGISTRY default
    label_end           VARCHAR(128)    NULL,     -- trunk's right-endpoint annotation
    sort_order          SMALLINT        NULL,
    creator_fk          VARCHAR(64)     NOT NULL,
    create_ts           TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts           TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_branches_project
        FOREIGN KEY (project_fk) REFERENCES build_projects (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_branches_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 3. builds (depends on branches)
-- ----------------------------------------------------------------------------

CREATE TABLE builds (
    id                      INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    branch_fk               INT             NOT NULL,
    position                SMALLINT        NOT NULL,    -- 0-indexed order within branch
    build_number            INT             NOT NULL,    -- B in M.m.B.b — computed at creation, stored
    branch_number           INT             NOT NULL DEFAULT 0, -- b in M.m.B.b — 0 for trunk
    dot_color               VARCHAR(32)     NULL,        -- green|red|yellow|gray (semantic overlay)
    approved_for_release    TINYINT(1)      NOT NULL DEFAULT 0,
    creator_fk              VARCHAR(64)     NOT NULL,
    create_ts               TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts               TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_builds_branch
        FOREIGN KEY (branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_builds_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_builds_branch_position UNIQUE KEY (branch_fk, position)
);

-- ----------------------------------------------------------------------------
-- 4. Deferred ALTERs for the two circular FKs
-- ----------------------------------------------------------------------------

ALTER TABLE branches
    ADD COLUMN parent_build_fk INT NULL,
    ADD CONSTRAINT fk_branches_parent_build
        FOREIGN KEY (parent_build_fk) REFERENCES builds (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE build_projects
    ADD COLUMN trunk_branch_fk INT NULL,
    ADD CONSTRAINT fk_build_projects_trunk_branch
        FOREIGN KEY (trunk_branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

-- ----------------------------------------------------------------------------
-- 5. customer_releases (depends on customers + builds)
-- ----------------------------------------------------------------------------

CREATE TABLE customer_releases (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    customer_fk     INT             NOT NULL,
    build_fk        INT             NOT NULL,
    release_notes   TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer_releases_customer
        FOREIGN KEY (customer_fk) REFERENCES customers (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_customer_releases_build
        FOREIGN KEY (build_fk) REFERENCES builds (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_customer_releases_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_customer_releases_customer_build UNIQUE KEY (customer_fk, build_fk)
);
