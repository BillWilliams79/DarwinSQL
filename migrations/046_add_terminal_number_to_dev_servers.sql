-- Migration 046: Add terminal_number column to dev_servers (req #2419)
--
-- Encodes the iTerm tty number (e.g. /dev/ttys005 → 5) of the Claude Code
-- session that owns each dev server. The /devops-devserver-start skill
-- captures it from `ps -o tty= -p $PPID` and passes it to claim_dev_server.
--
-- Surfaced in the Dev Servers view so the user can correlate a running
-- dev server to the iTerm window it lives in.
--
-- Nullable: pre-existing claims won't be backfilled, and any caller that
-- can't resolve a tty (no controlling terminal) leaves it NULL.

ALTER TABLE dev_servers
    ADD COLUMN terminal_number SMALLINT NULL AFTER pid;
