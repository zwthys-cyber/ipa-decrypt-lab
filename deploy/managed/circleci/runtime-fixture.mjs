// Public project-owned fixture. This validates delivery, never DRM decryption.
export const DRIVE_FIXTURE=Object.freeze({
 producer_source:"2896fff82275ef791e3703cc17ed9473c77b151a",
 producer_job:62,producer_workflow:"1c28d9d9-f709-4cb4-b9ae-f5f4413208a5",
 path:"arm64-ios-sample/ARMSample-unsigned.ipa",filename:"Migration_ARM_Probe.ipa",
 bytes:5496,sha256:"85025bd1cfea42339ed38b09e9580e1094b2949153c83c81e66d9b1ad9043e93"
});
export const FIXTURE_SCHEMA=`CREATE TABLE IF NOT EXISTS runtime_drive_fixtures(
 job_id TEXT PRIMARY KEY REFERENCES runtime_jobs(job_id),authorized INTEGER NOT NULL DEFAULT 0,
 cleanup_state TEXT NOT NULL DEFAULT 'waiting',file_id TEXT
);`;
