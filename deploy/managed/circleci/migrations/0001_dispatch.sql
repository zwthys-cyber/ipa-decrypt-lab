-- Isolated pilot only. Preserve every intent across restart; never delete to retry.
CREATE TABLE circleci_dispatches (
  job_id TEXT PRIMARY KEY REFERENCES pilot_jobs(job_id),
  owner_id TEXT NOT NULL,
  request_id TEXT NOT NULL UNIQUE CHECK(length(request_id)=32),
  source_sha TEXT NOT NULL CHECK(length(source_sha)=40),
  state TEXT NOT NULL CHECK(state IN ('intent','submitted','unknown','finished')),
  run_id TEXT UNIQUE,
  created_at INTEGER NOT NULL CHECK(created_at>=0),
  updated_at INTEGER NOT NULL CHECK(updated_at>=created_at),
  CHECK ((state IN ('submitted','finished') AND run_id IS NOT NULL)
      OR state IN ('intent','unknown'))
);
CREATE INDEX circleci_dispatch_active ON circleci_dispatches(state);
