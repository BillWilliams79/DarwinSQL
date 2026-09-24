-- 20260913064647_add_build_viz_event_datetimes_built_at_branched_at_released.sql
--
-- Req #3515: record WHEN build-visualizer events happened — a build ran, a
-- branch was cut, a build shipped to a customer.
--
-- darwin:targets = darwin_dev
--
-- PROBLEM.  The three Build Visualizer event tables carry only row-write audit
--           columns (`create_ts` / `update_ts`). Those say when a ROW was
--           written, not when the EVENT happened: simulated and imported data
--           is written in one burst (Exemplar's 15 main builds all carry
--           create_ts 2026-09-13 06:31:3x while they represent two weeks of
--           twice-daily builds), and an edit bumps update_ts. There is nowhere
--           to store the event time, so the visualizer cannot show it.
--
-- SHAPE.    One nullable DATETIME per event table, named for the event:
--             builds.built_at               when the build ran
--             branches.branched_at          when the branch was cut
--             customer_releases.released_at when the build shipped to the customer
--           Stored as UTC (RDS runs time_zone = UTC); displayed in Pacific.
--           DATETIME, not TIMESTAMP: the value is a user-supplied event time,
--           not a server clock — DATETIME carries no implicit session-zone
--           conversion and no auto-initialisation. NULL, no DEFAULT: NULL is a
--           real answer ("not recorded"), and a DEFAULT CURRENT_TIMESTAMP would
--           silently re-state create_ts as if it were the event time. The
--           writers (Build Visualizer UI, darwin-mcp) stamp the value when the
--           event is performed live. create_ts / update_ts are unchanged.
--
-- TARGET.   DARWIN_DEV ONLY. The Build Visualizer tables were dropped from
--           production `darwin` by migration 057 (req #2760) and live only in
--           `darwin_dev`, so the declaration above bans production outright.
--           Never write `USE <db>;` into this file (req #3196).
--
-- APPLY.    python3 DarwinSQL/scripts/load_sql.py \
--             DarwinSQL/migrations/20260913064647_add_build_viz_event_datetimes_built_at_branched_at_released.sql darwin_dev
--
-- Migration id 20260913064647 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

ALTER TABLE builds
    ADD COLUMN built_at DATETIME NULL AFTER external_id;

ALTER TABLE branches
    ADD COLUMN branched_at DATETIME NULL AFTER acceptance_test_status;

ALTER TABLE customer_releases
    ADD COLUMN released_at DATETIME NULL AFTER release_notes;
