-- Add latitude and longitude columns to the user table
ALTER TABLE user ADD COLUMN latitude REAL;
ALTER TABLE user ADD COLUMN longitude REAL;

-- Add latitude and longitude to medicine (if you haven't already run this)
-- ALTER TABLE medicine ADD COLUMN latitude REAL;
-- ALTER TABLE medicine ADD COLUMN longitude REAL;
