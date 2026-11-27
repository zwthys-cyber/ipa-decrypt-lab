-- Private link metadata only; do not store file contents or OAuth credentials in D1.
CREATE TABLE pilot_links (
  job_id TEXT PRIMARY KEY REFERENCES pilot_jobs(job_id),
  owner_id TEXT NOT NULL,
  file_id TEXT NOT NULL UNIQUE CHECK(length(file_id) BETWEEN 10 AND 160),
  filename TEXT NOT NULL CHECK(length(filename) BETWEEN 1 AND 160),
  bytes INTEGER NOT NULL CHECK(bytes BETWEEN 1 AND 2000000000),
  sha256 TEXT NOT NULL CHECK(length(sha256)=64),
  expires_at INTEGER NOT NULL CHECK(expires_at>0)
);
