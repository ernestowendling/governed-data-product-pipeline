# Five-minute review

Start from the repository root with a fresh database path. These commands do not need cloud credentials or a paid service.

## 1. Run the synthetic batch

```bash
python -m pipeline run data/synthetic-payments.csv --database work/review.db
python -m pipeline report --database work/review.db --output work/review-evidence.json
```

Inspect status PUBLISHED, 10 inserted rows and 2 invalid rows. Inspect quarantine reasons AMOUNT_FORMAT and CURRENCY_NOT_ALLOWED. The daily EUR metric should be 550000 cents across ten payments.

## 2. Replay it

Repeat the run command. Expect replayed=true and the same batch ID. Re-run the report: one batch, ten payments. This remains true if you rename the source without changing its bytes.

## 3. Follow a metric back to the source

```bash
python -m pipeline trace 2026-01-15 EUR --database work/review.db
```

The ten contributors identify payment ID, original batch ID, source record position and checksums. The sum of their amount_cents must equal the reported total. Each contributor also includes the exact contract JSON. Source bytes are retained in batches.source_bytes; their SHA-256 is source_sha.

The transform checksum covers core.py, schema.sql and metrics.sql. Retain the corresponding source-code revision with evidence exports.

## 4. Exercise failure and recovery

```bash
python -m unittest discover -s tests -v
```

Tests demonstrate a renamed required column blocking publication, excessive invalid records blocking the entire batch, corrected input publishing successfully, duplicate events avoiding inflation, conflicting values preserving prior facts and injected storage failure rolling back all writes.

The schema-failure test starts with an existing published payment and proves it remains unchanged. The quality-recovery test proves that both the original blocked decision and the successful corrected decision remain visible.

## 5. Read the decisions

- [Storage and money representation](adr/001-storage.md)
- [Batch orchestration and replay](adr/002-orchestration.md)
- [Contract enforcement and publication](adr/003-quality-gates.md)

The evidence files under examples are a captured local demonstration, not a live deployment or production dataset.

