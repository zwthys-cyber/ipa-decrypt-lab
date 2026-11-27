-- Preserve the original unknown intent. Only an explicitly audited empty probe can be retired.
CREATE TABLE circleci_probe_resolutions (
  job_id TEXT PRIMARY KEY REFERENCES circleci_dispatches(job_id),
  source_sha TEXT NOT NULL CHECK(length(source_sha)=40),
  reason TEXT NOT NULL CHECK(reason='audited_synthetic_noop'),
  resolved_at INTEGER NOT NULL
);
CREATE TABLE circleci_dispatch_diagnostics (
  job_id TEXT PRIMARY KEY REFERENCES circleci_dispatches(job_id),
  code TEXT NOT NULL,
  recorded_at INTEGER NOT NULL
);
