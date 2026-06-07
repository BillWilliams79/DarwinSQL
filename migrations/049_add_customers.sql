-- 049_add_customers.sql
--
-- Req #2604: Customer Release — add `customers` table.
--
-- A customer is a recipient of a build release (HP, NVIDIA, Cisco, Google, ...).
-- The Build Visualizer attaches `customer-release` branches to build dots to
-- visualize which customer received which sprint or end-release build.
--
-- FK policy:
--   creator_fk → profiles(id)  ON DELETE CASCADE

CREATE TABLE customers (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    customer_name   VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_customers_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
