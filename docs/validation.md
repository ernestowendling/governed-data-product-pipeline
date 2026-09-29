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

## Published CI validation

The [initial published commit](https://github.com/ernestowendling/governed-data-product-pipeline/commit/87c690e85b213285d0caead1823797b90b8ada7b) passed the [GitHub Actions run](https://github.com/ernestowendling/governed-data-product-pipeline/actions/runs/36593100876) on Python 3.11, 3.12 and 3.13. Each job ran all 15 behavioral tests, ingested the synthetic sample and exported the evidence report successfully.

## Not validated

Only Python 3.12 was exercised locally; the additional versions were exercised in GitHub Actions. Docker, PostgreSQL, dbt and cloud deployments are not implemented or tested.

