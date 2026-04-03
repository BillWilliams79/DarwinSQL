-- Strava activity IDs exceed INT max (2,147,483,647).
-- Widen route_id and run_id to BIGINT for Strava API imports.
ALTER TABLE map_routes MODIFY route_id BIGINT NOT NULL;
ALTER TABLE map_runs MODIFY run_id BIGINT NOT NULL;
