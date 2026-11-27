-- Retire an expired link without discarding its immutable receipt.
-- Apply with the isolated pilot disabled; no remote Drive operations.
ALTER TABLE pilot_links ADD COLUMN retired_at INTEGER CHECK(retired_at IS NULL OR (typeof(retired_at)='integer' AND retired_at>=expires_at));
