# Security And Access Control

## Local Single-user Mode

LifeSnap currently runs as a local single-user application. It does not expose
registration, login, or user bearer-session endpoints, and its business APIs
operate on the device's shared local workspace.

Do not expose this profile directly to an untrusted network. A future
multi-user deployment needs a separate authentication, authorization, and data
isolation design before it can safely serve more than one person.

## RAG Administration

RAG knowledge reads are available in the local workspace. Updating, resetting,
or rolling back the shared RAG knowledge base requires a short-lived
administrator session. `POST /agent/admin-session` exchanges the configured
`LIFESNAP_ADMIN_KEY` for that session; write requests send it as an
`Authorization: Bearer <admin-session-token>` header.

The optional local admin-key reveal endpoint remains disabled by default. It
requires `LIFESNAP_ALLOW_ADMIN_KEY_REVEAL=true` and a localhost request.

## Operational Notes

SQLite is a local/single-node persistence profile. Use PostgreSQL, an identity
provider, authorization policies, and database-backed session/revocation
strategy before horizontally scaling or enabling multi-user access.

Automated smoke tests cover unauthenticated single-user access, administrator
session enforcement for RAG writes, and core data workflows.
