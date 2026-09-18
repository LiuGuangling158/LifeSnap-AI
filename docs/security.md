# Security And Access Control

## Authentication

LifeSnap uses username and password accounts. Passwords are salted and derived
with scrypt; the database never stores a plaintext password. Successful login
and registration return an HMAC-signed bearer session. Set
LIFESNAP_AUTH_SESSION_SECRET to a long, unique secret in every deployed
environment and rotate it to invalidate existing sessions when needed.

The first account in a new local database is assigned the admin role so an
operator can initialize the RAG knowledge base. Later self-registered accounts
receive the user role. Public deployments should place registration behind an
approved onboarding flow before exposing the service.

## Authorization And Isolation

All business APIs except /health and /auth/* require a bearer session. Bills,
tasks, diaries, attachments, pending Agent candidates, settings, idempotency
records, audit events and data exports are scoped to the authenticated account.
The migration assigns pre-auth local data to the first account that is
registered.

Only admin accounts may update, reset or roll back the shared RAG knowledge
base. Normal users can retrieve knowledge used by their own Agent sessions, but
cannot change it. The optional historic admin key endpoint does not bypass
application login or the admin role.

## Operational Notes

SQLite is a local/single-node persistence profile. Its ownership migration is
transactional and the application serializes user-scoped store reloads to avoid
cross-account state in the local runtime. Use PostgreSQL plus a database-backed
session/revocation strategy before horizontally scaling the API.

Automated smoke tests cover anonymous rejection, first-admin bootstrap,
ordinary-user RAG denial and bidirectional bill isolation between two accounts.
