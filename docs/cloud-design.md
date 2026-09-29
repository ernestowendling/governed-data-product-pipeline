# Cloud deployment design — proposed, not implemented

The local MVP makes no claim of deployed cloud infrastructure, PostgreSQL/dbt execution or enterprise integration.

## Candidate deployment

Synthetic files arrive in a restricted object-storage container. A scheduled container job validates contracts and writes to managed PostgreSQL. dbt models materialize daily products. Separate jobs export evidence to access-controlled object storage. Managed identity supplies service access; secrets, where unavoidable, live in a secret manager.

## Decisions required before deployment

- Select a cloud and region based on actual workload, organizational requirements and service availability.
- Define owner-approved retention for source records, quarantine and decision evidence.
- Separate ingestion, exception review and product-consumption permissions.
- Choose expected volume, concurrency, freshness and recovery objectives.
- Benchmark the transaction and duplicate handling under representative load.
- Introduce schema migrations, restore tests, deployment rollback and monitoring alerts.
- Verify hosting and licensing requirements before publishing a live service.

## Cost model

No cost estimate is claimed without provider, region and workload inputs. Budget for database compute/storage/backups, container execution, object storage, logs and network transfer. Record measured batch duration, records processed, evidence growth and query load before sizing.

## Acceptance before claiming a cloud implementation

A repeatable infrastructure deployment, integration test run, permission-denial tests, retry/idempotency tests, restore exercise and measured workload report must exist. The local tests do not substitute for these checks.

