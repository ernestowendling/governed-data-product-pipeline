# ADR-001: SQLite and integer minor units for the local MVP

Status: Accepted for local MVP
Date: 2026-09-29
Deciders: Project implementation; revisit before hosted deployment

## Context

Reviewers need a reproducible pipeline without credentials or background services. The development environment has no running Docker engine. Synthetic amounts must aggregate without binary floating-point rounding.

## Decision

Use Python's standard-library SQLite driver. Store amounts as integer cents and aggregate each currency separately. Retain source bytes, contracts and decisions in the same local database.

## Options considered

| Option | Complexity | Cost | Scale | Familiarity requirement |
|---|---|---|---|---|
| SQLite | Low | Local disk | Single-writer local workload | Python and SQL |
| PostgreSQL with dbt | Medium | Local service or hosted instance | Multi-user service and richer transformations | Database operations and dbt |
| CSV-only outputs | Low initially | Local disk | Weak concurrent publication controls | File processing |

## Tradeoffs and consequences

SQLite offers easy review and transactional consistency; PostgreSQL is preferable when independent workers and authenticated services share a product. Files alone would require custom atomic publication and locking.

The chosen implementation has no migration engine or production access controls. Moving to PostgreSQL requires a schema migration, integration tests, money-type review, deduplication constraints and transaction-concurrency tests. dbt should own transformations when models and dependencies grow.

## Actions

- [x] Implement facts, quarantine and lineage tables.
- [x] Verify exact cents and transaction rollback.
- [ ] Implement and benchmark PostgreSQL/dbt before claiming those capabilities.

