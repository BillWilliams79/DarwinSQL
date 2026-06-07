-- 052_rename_dev_branches_label.sql
--
-- Req #2694: Build Visualizer second view + label cleanup.
--
-- Renames the default name for `development`-type branches from the old
-- plural "Development Branches" to the shortened "Dev Branch". The change
-- is purely cosmetic — the slug `branch_type='development'` is unchanged,
-- so no downstream reader needs to recompile. Only branches that still
-- carry the auto-generated default name are updated; user-renamed dev
-- branches (e.g. "Branch 20") are left alone.
--
-- Companion edits in the same req:
--   * Topology/build-visualizer/app.js     — REGISTRY label
--   * Topology/build-visualizer/builds.json — standalone seed data
--   * Darwin/src/BuildVisualizer/d3LayoutEngine.js — D3-view REGISTRY label
--   * Darwin/src/BuildVisualizer/sprintCyclePattern.js — generator default
--   * Darwin/src/BuildVisualizer/branchTypeChipStyles.js — toolbar chip label
--   * DarwinSQL/scripts/seed_build_projects.py — seed row for `dev-a`
--   * memory/build-visualizer-design.md — branch-type catalog row

UPDATE branches
   SET name = 'Dev Branch'
 WHERE branch_type = 'development'
   AND name = 'Development Branches';
