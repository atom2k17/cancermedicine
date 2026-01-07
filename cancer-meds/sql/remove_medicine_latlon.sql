-- Safe procedure to remove latitude/longitude columns from the `medicine` table in SQLite.
-- WARNING: Always back up your database before running schema-changing SQL.
-- Steps:
-- 1) Make a copy of your DB file first (outside SQLite):
--    copy site.db site.db.bak
-- 2) Run this script in DB Browser -> Execute SQL (or sqlite3 CLI). It recreates the table without the latitude/longitude columns and copies existing data.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Create new table without latitude/longitude
CREATE TABLE medicine_new (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    expiry_date DATE,
    type TEXT NOT NULL,
    status TEXT DEFAULT 'available',
    created_at DATETIME,
    proof TEXT,
    location TEXT,
    FOREIGN KEY(user_id) REFERENCES "user"(id)
);

-- Copy data from old table to new table (skip latitude/longitude)
INSERT INTO medicine_new (id, user_id, name, quantity, expiry_date, type, status, created_at, proof, location)
SELECT id, user_id, name, quantity, expiry_date, type, status, created_at, proof, location FROM medicine;

-- Drop old table and rename new
DROP TABLE medicine;
ALTER TABLE medicine_new RENAME TO medicine;

COMMIT;
PRAGMA foreign_keys = ON;

-- After running, inspect the schema:
-- PRAGMA table_info('medicine');
-- And verify related tables (matches) are fine.

-- NOTE: If you have indexes or triggers on the old table, recreate them here.
