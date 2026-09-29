PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS batches (
 batch_id TEXT PRIMARY KEY, source_name TEXT NOT NULL, source_sha TEXT NOT NULL,
 source_bytes BLOB NOT NULL, contract_sha TEXT NOT NULL, contract_json TEXT NOT NULL,
 transform_sha TEXT NOT NULL, created_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('PUBLISHED','BLOCKED_SCHEMA','BLOCKED_QUALITY')),
 total_rows INTEGER NOT NULL, inserted_rows INTEGER NOT NULL, duplicate_rows INTEGER NOT NULL,
 invalid_rows INTEGER NOT NULL, message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
 payment_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, paid_date TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents > 0), currency TEXT NOT NULL,
 record_sha TEXT NOT NULL, batch_id TEXT NOT NULL REFERENCES batches(batch_id),
 source_row INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
 batch_id TEXT NOT NULL REFERENCES batches(batch_id), source_row INTEGER NOT NULL,
 payment_id TEXT NOT NULL REFERENCES payments(payment_id),
 outcome TEXT NOT NULL CHECK(outcome IN ('INSERTED','DUPLICATE')),
 PRIMARY KEY(batch_id, source_row)
);
CREATE TABLE IF NOT EXISTS quarantine (
 batch_id TEXT NOT NULL REFERENCES batches(batch_id), source_row INTEGER NOT NULL,
 raw_json TEXT NOT NULL, reasons_json TEXT NOT NULL, PRIMARY KEY(batch_id, source_row)
);

