-- Isolated pilot database. Never apply to the existing production state.
CREATE TABLE pilot_jobs (
  job_id TEXT PRIMARY KEY CHECK (length(job_id)=38 AND substr(job_id,1,6)='pilot_'),
  owner_id TEXT NOT NULL,
  update_id INTEGER NOT NULL CHECK (update_id>=0),
  app_id TEXT NOT NULL CHECK (length(app_id) BETWEEN 5 AND 20),
  region TEXT NOT NULL CHECK (region IN ('cn','default')),
  day INTEGER NOT NULL CHECK (day>=0),
  created_at INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('waiting_for_runtime','cancelled')),
  UNIQUE(owner_id,update_id)
);
CREATE INDEX pilot_daily ON pilot_jobs(owner_id,day);
CREATE INDEX pilot_active ON pilot_jobs(owner_id,state);
CREATE INDEX pilot_recent ON pilot_jobs(owner_id,created_at DESC,job_id DESC);
