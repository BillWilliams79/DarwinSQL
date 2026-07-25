-- 071_instruction_english_titles.sql
--
-- Req #3068 — rewrite `instructions.name` from kebab-case slug to an English
-- title. DML ONLY: no schema change, no DDL.
--
-- WHY THIS IS SAFE. Nothing machine-reads `instructions.name`. Verified across the
-- whole workspace during req #3063: no code path, script, hook, skill, MCP
-- resource URI, REST route or test resolves an instruction by name. Every MCP
-- mutation takes an integer id, `list_instructions_for_agent` joins on
-- `ai.instruction_fk = i.id`, and the boot payload composes by agent id. The one
-- `WHERE name =` helper (darwin-mcp/db.py get_instruction_by_name) has a single
-- caller, a test that generates its own uuid name.
--
-- DO NOT GENERALISE THIS TO `agents.name`. That one IS a machine identifier —
-- `darwin://agents/{name}` is name-addressed. There is no
-- `darwin://instructions/{name}`.
--
-- Keyed by the OLD NAME, not by id, on purpose: `darwin` and `darwin_dev` were
-- seeded independently and their instruction ids do NOT correspond. Production
-- carries 78 rows; darwin_dev carries the same 76 plus neither of
-- 'common-root-cause-debugging-loop' nor 'common-root-cause-five-whys'. Every
-- statement is therefore an id-free, idempotent no-op when the row is absent or
-- already renamed.
--
-- Every word of the slug is preserved, dashes become spaces, and the first word is
-- capitalised. The domain prefix is deliberately KEPT: it says which architect
-- family the rule belongs to, and keeping it means a name sort still groups the
-- catalog by domain. Acronyms are cased properly (AWS, MCP, E2E, DnD, JWT, MUI,
-- KML, BIGINT, NVIDIA, CLAUDE.md, creator_fk, TouchBackend, afterAll, z-order).
--
-- The 35 prose references to the six previously-referenced slugs are migrated in
-- the same PR — the twelve agent charter stubs, memory/agent-charter-template.md,
-- memory/agents-registry.md, memory/root-cause-debugging.md and
-- memory/code-reviewer-charter.md.
--
-- APPLY TO darwin_dev FIRST, verify, then production.
--   mysql -h $endpoint -u $username -p$db_password darwin_dev < 071_instruction_english_titles.sql
--   mysql -h $endpoint -u $username -p$db_password darwin     < 071_instruction_english_titles.sql


UPDATE instructions SET name = 'Applications disclose scheduler cost' WHERE name = 'applications-disclose-scheduler-cost';
UPDATE instructions SET name = 'Applications format detector order is load bearing' WHERE name = 'applications-format-detector-order-is-load-bearing';
UPDATE instructions SET name = 'Applications KML MyMaps constraints' WHERE name = 'applications-kml-mymaps-constraints';
UPDATE instructions SET name = 'Applications no Wahoo cloud API' WHERE name = 'applications-no-wahoo-cloud-api';
UPDATE instructions SET name = 'Applications Strava limits and BIGINT ids' WHERE name = 'applications-strava-limits-and-bigint-ids';
UPDATE instructions SET name = 'AWS console built no IaC' WHERE name = 'aws-console-built-no-iac';
UPDATE instructions SET name = 'AWS never quote stored cost figures' WHERE name = 'aws-never-quote-stored-cost-figures';
UPDATE instructions SET name = 'AWS no new cost without disclosure' WHERE name = 'aws-no-new-cost-without-disclosure';
UPDATE instructions SET name = 'Builds common label size and location' WHERE name = 'builds-common-label-size-and-location';
UPDATE instructions SET name = 'Builds exemplar is load bearing' WHERE name = 'builds-exemplar-is-load-bearing';
UPDATE instructions SET name = 'Builds geometry from registry only' WHERE name = 'builds-geometry-from-registry-only';
UPDATE instructions SET name = 'Builds no autonomous deploy' WHERE name = 'builds-no-autonomous-deploy';
UPDATE instructions SET name = 'Builds reserved branch number ranges' WHERE name = 'builds-reserved-branch-number-ranges';
UPDATE instructions SET name = 'Builds standalone parity is required' WHERE name = 'builds-standalone-parity-is-required';
UPDATE instructions SET name = 'Builds version engine is authority' WHERE name = 'builds-version-engine-is-authority';
UPDATE instructions SET name = 'Code review diligence changed paths' WHERE name = 'code-review-diligence-changed-paths';
UPDATE instructions SET name = 'Code review mental simulation' WHERE name = 'code-review-mental-simulation';
UPDATE instructions SET name = 'Code review partner specialists' WHERE name = 'code-review-partner-specialists';
UPDATE instructions SET name = 'Code review report format and severity' WHERE name = 'code-review-report-format-and-severity';
UPDATE instructions SET name = 'Code review report not modify' WHERE name = 'code-review-report-not-modify';
UPDATE instructions SET name = 'Common documents' WHERE name = 'common-documents';
UPDATE instructions SET name = 'Common root cause debugging loop' WHERE name = 'common-root-cause-debugging-loop';
UPDATE instructions SET name = 'Common root cause five whys' WHERE name = 'common-root-cause-five-whys';
UPDATE instructions SET name = 'Darwin curating does not transfer ownership' WHERE name = 'darwin-curating-does-not-transfer-ownership';
UPDATE instructions SET name = 'Darwin delegate then synthesize' WHERE name = 'darwin-delegate-then-synthesize';
UPDATE instructions SET name = 'Darwin domain model coherence' WHERE name = 'darwin-domain-model-coherence';
-- Hand-corrected title (a bare de-slug read 'non negotiable'):
UPDATE instructions SET name = 'Darwin hard gates are non-negotiable' WHERE name = 'darwin-hard-gates-non-negotiable';
UPDATE instructions SET name = 'Darwin label epistemic status' WHERE name = 'darwin-label-epistemic-status';
UPDATE instructions SET name = 'Darwin present tradeoffs honestly' WHERE name = 'darwin-present-tradeoffs-honestly';
UPDATE instructions SET name = 'Darwin simplest correct solution' WHERE name = 'darwin-simplest-correct-solution';
UPDATE instructions SET name = 'Data creator_fk tables discipline' WHERE name = 'data-creator-fk-tables-discipline';
UPDATE instructions SET name = 'Data mandatory AWS consult for API Gateway' WHERE name = 'data-mandatory-aws-consult-for-api-gateway';
UPDATE instructions SET name = 'Data migration hard gate' WHERE name = 'data-migration-hard-gate';
UPDATE instructions SET name = 'Data never confuse the two databases' WHERE name = 'data-never-confuse-the-two-databases';
UPDATE instructions SET name = 'Data REST conventions are a contract' WHERE name = 'data-rest-conventions-are-a-contract';
UPDATE instructions SET name = 'Data schema of record parity guardian' WHERE name = 'data-schema-of-record-parity-guardian';
UPDATE instructions SET name = 'Frontend API calls outside state updaters' WHERE name = 'frontend-api-calls-outside-state-updaters';
UPDATE instructions SET name = 'Frontend devserver via skill only' WHERE name = 'frontend-devserver-via-skill-only';
UPDATE instructions SET name = 'Frontend DnD libraries are not interchangeable' WHERE name = 'frontend-dnd-libraries-are-not-interchangeable';
UPDATE instructions SET name = 'Frontend invalidate after mutation resolves' WHERE name = 'frontend-invalidate-after-mutation-resolves';
UPDATE instructions SET name = 'Frontend never legacy peer deps' WHERE name = 'frontend-never-legacy-peer-deps';
UPDATE instructions SET name = 'Frontend preserve E2E testids' WHERE name = 'frontend-preserve-e2e-testids';
UPDATE instructions SET name = 'Frontend sort format is colon separated' WHERE name = 'frontend-sort-format-is-colon-separated';
UPDATE instructions SET name = 'Frontend template row pattern' WHERE name = 'frontend-template-row-pattern';
UPDATE instructions SET name = 'Memory CLAUDE.md hard gates immutable' WHERE name = 'memory-claude-md-hard-gates-immutable';
UPDATE instructions SET name = 'Memory do not memorize derivable' WHERE name = 'memory-do-not-memorize-derivable';
UPDATE instructions SET name = 'MEMORY.md line budget' WHERE name = 'memory-md-line-budget';
UPDATE instructions SET name = 'Memory structure not domain facts' WHERE name = 'memory-structure-not-domain-facts';
UPDATE instructions SET name = 'Memory verify before acting on stale' WHERE name = 'memory-verify-before-acting-on-stale';
UPDATE instructions SET name = 'Swarm adjacent code blocks collapse' WHERE name = 'swarm-adjacent-code-blocks-collapse';
UPDATE instructions SET name = 'Swarm closing skills are user initiated' WHERE name = 'swarm-closing-skills-are-user-initiated';
UPDATE instructions SET name = 'Swarm conflicts resolve in band' WHERE name = 'swarm-conflicts-resolve-in-band';
UPDATE instructions SET name = 'Swarm hygiene private helpers are private' WHERE name = 'swarm-hygiene-private-helpers-are-private';
UPDATE instructions SET name = 'Swarm never delete git internals' WHERE name = 'swarm-never-delete-git-internals';
UPDATE instructions SET name = 'Swarm shell state does not persist' WHERE name = 'swarm-shell-state-does-not-persist';
UPDATE instructions SET name = 'Swarm skill design patterns' WHERE name = 'swarm-skill-design-patterns';
UPDATE instructions SET name = 'Swarm verify status transitions' WHERE name = 'swarm-verify-status-transitions';
UPDATE instructions SET name = 'Systems always via wrapper MCP calls' WHERE name = 'systems-always-via-wrapper-mcp-calls';
UPDATE instructions SET name = 'Systems Cognito config invariants' WHERE name = 'systems-cognito-config-invariants';
UPDATE instructions SET name = 'Systems creator_fk resolution must match both ways' WHERE name = 'systems-creator-fk-resolution-must-match-both-ways';
UPDATE instructions SET name = 'Systems MCP URI params are percent encoded' WHERE name = 'systems-mcp-uri-params-are-percent-encoded';
UPDATE instructions SET name = 'Systems never add a tool where a resource works' WHERE name = 'systems-never-add-a-tool-where-a-resource-works';
UPDATE instructions SET name = 'Systems preserve JWT profile merge' WHERE name = 'systems-preserve-jwt-profile-merge';
UPDATE instructions SET name = 'Systems serialized decorator mandatory' WHERE name = 'systems-serialized-decorator-mandatory';
UPDATE instructions SET name = 'Test known conftest drift do not fix casually' WHERE name = 'test-known-conftest-drift-do-not-fix-casually';
UPDATE instructions SET name = 'Test MUI testid lands on the wrapper' WHERE name = 'test-mui-testid-lands-on-the-wrapper';
UPDATE instructions SET name = 'Test never assume afterAll runs' WHERE name = 'test-never-assume-afterall-runs';
UPDATE instructions SET name = 'Test never run full E2E during implementation' WHERE name = 'test-never-run-full-e2e-during-implementation';
UPDATE instructions SET name = 'Test serial only when state is shared' WHERE name = 'test-serial-only-when-state-is-shared';
UPDATE instructions SET name = 'Test TouchBackend needs mouse events' WHERE name = 'test-touchbackend-needs-mouse-events';
UPDATE instructions SET name = 'Topology data and factories first' WHERE name = 'topology-data-and-factories-first';
UPDATE instructions SET name = 'Topology flipped orientation scope' WHERE name = 'topology-flipped-orientation-scope';
UPDATE instructions SET name = 'Topology incremental edits no autonomous deploy' WHERE name = 'topology-incremental-edits-no-autonomous-deploy';
UPDATE instructions SET name = 'Topology layout and z-order invariants' WHERE name = 'topology-layout-and-zorder-invariants';
UPDATE instructions SET name = 'Topology mirror vendored copies same PR' WHERE name = 'topology-mirror-vendored-copies-same-pr';
UPDATE instructions SET name = 'Topology NVIDIA numbers are ground truth' WHERE name = 'topology-nvidia-numbers-are-ground-truth';
UPDATE instructions SET name = 'Topology palette is mandatory' WHERE name = 'topology-palette-is-mandatory';
UPDATE instructions SET name = 'Topology watch for orphan references' WHERE name = 'topology-watch-for-orphan-references';

-- Verification: expect 0 rows still holding a dashed slug.
-- SELECT id, name FROM instructions WHERE name LIKE '%-%' AND name NOT LIKE '% %';
