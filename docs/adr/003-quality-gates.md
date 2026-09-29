# ADR-003: Fail closed on schema breaks; quarantine row exceptions

Status: Accepted for local MVP
Date: 2026-09-29
Deciders: Project implementation; threshold is illustrative

## Context

Silently accepting new column meanings or unsupported contract versions undermines data governance. Some isolated record errors should be inspectable without obscuring the whole batch.

## Decision

Require the exact supported schema. Quarantine invalid rows. Publish valid rows only when the invalid fraction is at most the contract threshold. Block the whole batch above that threshold and retain its evidence. Duplicate IDs with conflicting contents are errors.

## Options considered

| Option | Complexity | Cost | Scale | Familiarity requirement |
|---|---|---|---|---|
| Explicit Python rules + JSON contract | Low | Local execution | Bounded batches | Python and JSON |
| Quality framework | Medium | Additional dependencies | Larger rule catalogues | Framework-specific concepts |
| Accept all and report later | Low at ingestion | Downstream correction risk | Easy ingestion | Consumers must compensate |

## Tradeoffs and consequences

Explicit rules keep decisions easy to inspect but demand discipline as the rule catalogue expands. The 25% threshold is solely a synthetic demonstration setting. Production thresholds need a documented decision by a data owner and use-case-specific expectations.

Schema errors preserve original bytes at batch level. They do not produce a misleading row-level interpretation of a malformed source. Quality-blocked records can be corrected and resubmitted; already published records need a future governed correction design.

## Actions

- [x] Exercise schema breaks, invalid dates/amounts/currencies and quality recovery.
- [x] Export reasons and rule fingerprints.
- [ ] Add enforced review workflows and schema migration policy for hosted operation.

