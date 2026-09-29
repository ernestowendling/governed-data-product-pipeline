# ADR-002: Content-addressed synchronous batches

Status: Accepted for local MVP
Date: 2026-09-29
Deciders: Project implementation

## Context

Input files may be retried, renamed or overlap earlier deliveries. A local reviewer needs deterministic outcomes without a scheduler.

## Decision

Use a synchronous CLI. Batch identity hashes source bytes, canonical contract and transformation checksum. A database transaction serializes identity checks and writes. Payment keys prevent duplication across distinct batches.

## Options considered

| Option | Complexity | Cost | Scale | Familiarity requirement |
|---|---|---|---|---|
| CLI plus content identity | Low | One local process | Bounded local batches | Python |
| Scheduler such as Airflow | High for this scope | Service operation | Multiple dependencies and scheduled runs | Orchestration operations |
| Streaming ingestion | High | Broker and consumers | Continuous events | Stream processing |

## Tradeoffs and consequences

A filename or timestamp cannot safely identify replay. Content identity is deterministic but different byte formatting creates a different batch. Event-level deduplication handles that case.

The design is incremental by previously unseen payment IDs, not a date watermark. Late-arriving new IDs can publish. Conflicts require investigation. Technical failures are process failures, not persisted completed batches. External retries are bounded by database busy timeout; automated retry/backoff is future work.

## Actions

- [x] Test exact replay, overlapping batches and concurrent replay.
- [x] Test rollback and corrected-input recovery.
- [ ] Introduce a scheduler only when real dependencies justify it.

