# ADR 001 — Local demo and PostgreSQL deployment

Status: accepted for the pilot.

Keep the application a modular monolith. The installable service uses PostgreSQL for business records and LangGraph checkpoints. A local DEMO may use SQLite so the complete workflow runs on a machine without a database service. Both paths use the same domain rules and API. The SQLite path is a developer demonstration and does not establish PostgreSQL concurrency or recovery behavior; those checks must be repeated against the deployment stack.
