# ADR 002 — Version-bound review and approval

Status: accepted.

An extraction or correction creates a new document version. Findings and review decisions refer to that version. Approval records the version identifier and content hash; an edit invalidates the previous approval. Export rechecks scope, role, status, and version in the same use case that claims an idempotent export key. Graph review is a pause point, while external writes occur in separate steps so resuming a node does not repeat them.
