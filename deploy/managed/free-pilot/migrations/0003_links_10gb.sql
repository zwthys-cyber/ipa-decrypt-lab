-- Expand the isolated link metadata cap to 10 decimal GB.
-- Retain all existing rows, expiry timestamps and ownership restrictions.
-- Apply as a D1 migration transaction with the pilot disabled.
CREATE TABLE pilot_links_v2 (
  job_id TEXT PRIMARY KEY REFERENCES pilot_jobs(job_id),
  owner_id TEXT NOT NULL,
  file_id TEXT NOT NULL UNIQUE CHECK(length(file_id) BETWEEN 10 AND 160),
  filename TEXT NOT NULL CHECK(length(filename) BETWEEN 1 AND 160),
  bytes INTEGER NOT NULL CHECK(typeof(bytes)='integer' AND bytes BETWEEN 1 AND 10000000000),
  sha256 TEXT NOT NULL CHECK(length(sha256)=64),
  expires_at INTEGER NOT NULL CHECK(expires_at>0)
);
INSERT INTO pilot_links_v2(job_id,owner_id,file_id,filename,bytes,sha256,expires_at)
SELECT job_id,owner_id,file_id,filename,bytes,sha256,expires_at FROM pilot_links;
DROP TABLE pilot_links;
ALTER TABLE pilot_links_v2 RENAME TO pilot_links;
