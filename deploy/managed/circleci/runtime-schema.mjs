// Independent production-candidate tables; legacy pilot and source evidence remain unchanged.
export const RUNTIME_SCHEMA=`
CREATE TABLE IF NOT EXISTS runtime_jobs(
 job_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,
 profile TEXT NOT NULL CHECK(profile IN ('default','cn','tf')),
 kind TEXT NOT NULL CHECK(kind IN ('fixture','export')),
 target TEXT NOT NULL,version TEXT NOT NULL,source_sha TEXT NOT NULL,
 state TEXT NOT NULL,created_at INTEGER NOT NULL,deadline INTEGER NOT NULL,
 run_id TEXT UNIQUE,worker_job_id TEXT UNIQUE,workflow_id TEXT,
 dispatch_nonce TEXT UNIQUE,finished_at INTEGER,fixture_verified INTEGER NOT NULL DEFAULT 0,
 plaintext_sha256 TEXT,plaintext_bytes INTEGER,filename TEXT,
 file_id TEXT,link_expires INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS runtime_one_fixture_per_owner ON runtime_jobs(owner_id) WHERE kind='fixture';
CREATE TABLE IF NOT EXISTS runtime_credential_leases(
 job_id TEXT PRIMARY KEY REFERENCES runtime_jobs(job_id),context_json TEXT NOT NULL,expires_at INTEGER NOT NULL,
 ciphertext TEXT,cipher_sha256 TEXT,publisher_run_id TEXT UNIQUE,published_at INTEGER,consumed_at INTEGER
);
CREATE TABLE IF NOT EXISTS runtime_publisher_dispatches(
 job_id TEXT PRIMARY KEY REFERENCES runtime_jobs(job_id),state TEXT NOT NULL,created_at INTEGER NOT NULL
);
`;
