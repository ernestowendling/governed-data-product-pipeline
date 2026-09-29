# Architecture

## Boundaries

The input boundary is a UTF-8 CSV file and an explicitly selected JSON contract. The output is a daily claims-payment aggregate grouped by date and currency. Synthetic policy IDs form the reference-data boundary.

The CLI delegates to a small deterministic validation layer. SQL implements storage and aggregation. No AI service participates in quality decisions.

## Data layers

1. **Source evidence:** batches retains source bytes and SHA-256, contract JSON/hash, transformation hash, timestamps, decision and counts.
2. **Governed facts:** payments stores validated records in integer cents, keyed by immutable payment ID.
3. **Lineage observations:** observations links each valid source record to a payment and labels insertion versus duplicate.
4. **Exceptions:** quarantine retains raw values and machine-readable reasons. Entire quality-blocked batches are quarantined. Structurally malformed sources remain in batch evidence.
5. **Product:** metrics.sql aggregates the governed facts; trace returns contributing rows.

## Transaction boundary

Schema parsing and contract validation precede the write transaction. The writer acquires BEGIN IMMEDIATE before checking batch identity and existing payment keys. Thus overlapping writers cannot both decide an event is absent and insert it independently.

Batch decision, facts, observations and quarantine are committed atomically. A technical exception rolls back everything. Reports and traces run within read transactions for a consistent local snapshot. No success evidence is written outside the data transaction.

## Rule identity

Canonical JSON makes formatting-only contract changes identity-neutral. The transformation checksum covers the exact bytes of core.py, schema.sql and metrics.sql; formatting changes in those files therefore create a distinct transformation identity. The source checksum covers exact bytes, including newline style.

Exact replay returns the existing decision. Across different batches the primary key and record checksum distinguish duplicate events from conflicting events. Canonical amounts normalize 100, 100.0 and 100.00 to the same integer cents.

## Ownership

Claims Data Owner accepts the product purpose and threshold policy. Claims Data Steward reviews exceptions and proposes remediation. Platform Operator runs the pipeline and investigates technical failures. These are documented responsibilities, not application-enforced roles.

## Tradeoffs and limitations

The implementation retains all source bytes and exception values for inspectability; it has no retention policy enforcement. It intentionally fails closed on unsupported contract versions and unknown contract fields. Extra/missing/reordered CSV columns block publication.

Published records are append-only through this interface. Contract changes affect new ingestion, not historical eligibility. There is no bitemporal history, automatic correction or deletion API. Physical database access can bypass application controls.

See the ADRs for accepted decisions and the separate cloud design for unimplemented capabilities.

## Technical references

- [Python sqlite3 transaction controls](https://docs.python.org/3/library/sqlite3.html)
- [SQLite transactions and immediate writers](https://www.sqlite.org/lang_transaction.html)

