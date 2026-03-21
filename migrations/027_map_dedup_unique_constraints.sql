-- UNIQUE constraints to prevent duplicate imports at DB level
ALTER TABLE map_routes ADD UNIQUE KEY uq_creator_route (creator_fk, route_id);
ALTER TABLE map_runs ADD UNIQUE KEY uq_creator_run (creator_fk, run_id);

-- Source column: tracks import origin so dedup cutoff is per-source.
-- Each source (platform/method) maintains its own independent import cutoff.
-- Values: 'cyclemeter' (bulk Meter.db), 'strava' (Strava bulk), 'gpx' (single GPX file), etc.
ALTER TABLE map_runs ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'cyclemeter' AFTER notes;
