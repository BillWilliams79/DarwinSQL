-- Migration 028: Add deferred state to priorities
-- Adds a "deferred" lifecycle state for priorities that were investigated but not implemented.
-- Deferred is mutually exclusive with closed (application-enforced, not DB constraint).

ALTER TABLE priorities
  ADD COLUMN deferred TINYINT(1) NOT NULL DEFAULT 0 AFTER closed,
  ADD COLUMN deferred_at TIMESTAMP NULL AFTER completed_at;
