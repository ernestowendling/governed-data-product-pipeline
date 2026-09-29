# Validation record

Date: 2026-09-29
Environment: Windows, Python 3.12.14, standard-library SQLite

## Observed results

- 15 behavioral tests passed locally.
- Synthetic input: 12 records.
- First ingestion: PUBLISHED; 10 inserted, 2 invalid, 0 duplicates.
- Expected metric verified by an automated test: 550000 EUR cents across 10 payments.
- Tests verified exact replay, overlapping batches, conflicting identities, schema blocking, invalid values, quality-gate recovery, concurrent replay, CLI failure status and mid-transaction rollback.

A test initially held a database connection open during temporary-directory cleanup on Windows. The test now explicitly closes that connection; the successful run above followed that correction.

## Evidence

- [Sample report](../examples/evidence.json)
- [Metric lineage](../examples/lineage.json)
- [Replay response](../examples/replay.json)

These files are captured outputs from the local synthetic demonstration. Runtime timestamps and hashes are evidence, not performance benchmarks.

## Not validated

The GitHub Actions workflow has been authored but has not run remotely. Only Python 3.12 was exercised locally. Docker, PostgreSQL, dbt and cloud deployments are not implemented or tested.

